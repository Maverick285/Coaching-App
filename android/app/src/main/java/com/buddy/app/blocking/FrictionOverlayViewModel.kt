package com.buddy.app.blocking

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.OverrideRedeemRequest
import com.buddy.app.data.OverrideRequestCreate
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class FrictionPhase {
    WAITING,            // tier 3 — 60s pause + reason field
    READY_TO_PROCEED,   // tier 3 — countdown done
    PROMPT_OVERRIDE,    // tier 4 — request override (or close)
    REQUESTING,         // POST /overrides in flight
    AWAITING_CODE,      // SMS sent (or echoed in dev); user enters code
    REDEEMING,          // POST /overrides/{id}/redeem in flight
    OVERRIDDEN,         // window open; can dismiss
    ERROR,
}

data class FrictionUiState(
    val packageName: String = "",
    val goalId: Int = 0,
    val sessionId: Int = 0,
    val blockTier: Int = 3,
    val phase: FrictionPhase = FrictionPhase.WAITING,
    val secondsRemaining: Int = 60,
    val reason: String = "",
    val overrideId: Int? = null,
    val codeDevEcho: String? = null,
    val codeInput: String = "",
    val message: String? = null,
    val error: String? = null,
)

class FrictionOverlayViewModel(
    application: Application,
    holder: ApiHolder,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(FrictionUiState())
    val state: StateFlow<FrictionUiState> = _state.asStateFlow()

    private var api: BuddyApi? = null

    init {
        viewModelScope.launch {
            holder.apiFlow.collectLatest { value: BuddyApi? -> api = value }
        }
    }

    fun init(packageName: String, goalId: Int, sessionId: Int, blockTier: Int) {
        _state.update {
            it.copy(
                packageName = packageName,
                goalId = goalId,
                sessionId = sessionId,
                blockTier = blockTier,
                phase = if (blockTier == 4) FrictionPhase.PROMPT_OVERRIDE else FrictionPhase.WAITING,
                secondsRemaining = if (blockTier == 4) 0 else 60,
            )
        }
        if (blockTier == 3) startCountdown()
    }

    fun setReason(value: String) = _state.update { it.copy(reason = value) }
    fun setCode(value: String) = _state.update { it.copy(codeInput = value.filter { ch -> ch.isDigit() }.take(6)) }

    fun proceedAfterFriction() {
        // Tier 3: user sat through the pause. Just close — the app they
        // tried to open is still in the foreground behind us.
        _state.update { it.copy(phase = FrictionPhase.READY_TO_PROCEED) }
    }

    fun openOverrideRequest() {
        val a = api ?: return
        val s = _state.value
        viewModelScope.launch {
            _state.update { it.copy(phase = FrictionPhase.REQUESTING, error = null) }
            try {
                val resp = a.requestOverride(
                    OverrideRequestCreate(
                        packageName = s.packageName,
                        reason = s.reason.ifBlank { "(no reason)" },
                        sessionId = s.sessionId.takeIf { it > 0 },
                        goalId = s.goalId.takeIf { it > 0 },
                    )
                )
                _state.update {
                    it.copy(
                        phase = FrictionPhase.AWAITING_CODE,
                        overrideId = resp.id,
                        codeDevEcho = resp.codeDevEcho,
                        message = if (resp.codeDevEcho != null) {
                            "Dev mode — code is ${resp.codeDevEcho}."
                        } else {
                            "${resp.approverLabel} should have a text. Ask them for the code."
                        },
                    )
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(phase = FrictionPhase.ERROR, error = e.message ?: "request failed")
                }
            }
        }
    }

    fun redeemCode() {
        val a = api ?: return
        val s = _state.value
        val id = s.overrideId ?: return
        viewModelScope.launch {
            _state.update { it.copy(phase = FrictionPhase.REDEEMING, error = null) }
            try {
                val resp = a.redeemOverride(id, OverrideRedeemRequest(code = s.codeInput))
                if (resp.success) {
                    BlockState.update(
                        blocks = emptyList(),
                        overrideOpen = true,
                        overrideExpiresAtMs = System.currentTimeMillis()
                            + (resp.request.activeMinutes * 60_000L),
                    )
                    _state.update {
                        it.copy(
                            phase = FrictionPhase.OVERRIDDEN,
                            message = "Override active for ${resp.request.activeMinutes} minutes.",
                        )
                    }
                } else {
                    _state.update {
                        it.copy(
                            phase = FrictionPhase.AWAITING_CODE,
                            error = resp.message,
                        )
                    }
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(phase = FrictionPhase.ERROR, error = e.message ?: "redeem failed")
                }
            }
        }
    }

    fun reset() {
        _state.update { FrictionUiState() }
    }

    private fun startCountdown() {
        viewModelScope.launch {
            while (true) {
                val cur = _state.value
                if (cur.phase != FrictionPhase.WAITING) return@launch
                if (cur.secondsRemaining <= 0) {
                    _state.update { it.copy(phase = FrictionPhase.READY_TO_PROCEED) }
                    return@launch
                }
                delay(1000)
                _state.update { it.copy(secondsRemaining = (it.secondsRemaining - 1).coerceAtLeast(0)) }
            }
        }
    }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer { FrictionOverlayViewModel(app, ApiHolder(app)) }
        }
    }
}

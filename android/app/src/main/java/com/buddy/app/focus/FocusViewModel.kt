package com.buddy.app.focus

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.FocusEnd
import com.buddy.app.data.FocusSession
import com.buddy.app.data.FocusStart
import com.buddy.app.data.Goal
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class FocusUiState(
    val configured: Boolean = false,
    val active: FocusSession? = null,
    val recent: List<FocusSession> = emptyList(),
    val goals: List<Goal> = emptyList(),
    val intention: String = "",
    val plannedMinutes: Int = 45,
    val selectedGoalId: Int? = null,
    val starting: Boolean = false,
    val ending: Boolean = false,
    val error: String? = null,
)

class FocusViewModel(
    application: Application,
    holder: ApiHolder,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(FocusUiState())
    val state: StateFlow<FocusUiState> = _state.asStateFlow()

    private var api: BuddyApi? = null

    init {
        viewModelScope.launch {
            holder.apiFlow.collectLatest { value: BuddyApi? ->
                api = value
                _state.update { it.copy(configured = value != null) }
                if (value != null) refresh()
            }
        }
    }

    fun refresh() {
        val a = api ?: return
        viewModelScope.launch {
            try {
                val active = a.activeFocus().session
                val recent = a.recentFocus(20)
                val goals = a.listGoals().goals.filter { it.state == "active" }
                _state.update {
                    it.copy(active = active, recent = recent, goals = goals, error = null)
                }
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun setIntention(value: String) = _state.update { it.copy(intention = value) }
    fun setMinutes(value: Int) = _state.update { it.copy(plannedMinutes = value.coerceIn(5, 240)) }
    fun setGoal(id: Int?) = _state.update { it.copy(selectedGoalId = id) }
    fun onClearError() = _state.update { it.copy(error = null) }

    fun start() {
        val a = api ?: return
        val s = _state.value
        if (s.intention.isBlank()) {
            _state.update { it.copy(error = "Set an intention first.") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(starting = true, error = null) }
            try {
                val session = a.startFocus(
                    FocusStart(
                        intention = s.intention.trim(),
                        plannedDurationMinutes = s.plannedMinutes,
                        goalId = s.selectedGoalId,
                    )
                )
                FocusSessionService.start(
                    getApplication(),
                    sessionId = session.id,
                    intention = session.intention,
                    plannedMinutes = session.plannedDurationMinutes,
                )
                _state.update {
                    it.copy(starting = false, active = session, intention = "")
                }
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(starting = false, error = e.message) }
            }
        }
    }

    fun end(summary: String = "") {
        val a = api ?: return
        val active = _state.value.active ?: return
        viewModelScope.launch {
            _state.update { it.copy(ending = true, error = null) }
            try {
                val ended = a.endFocus(active.id, FocusEnd(summary = summary))
                FocusSessionService.stop(getApplication())
                _state.update {
                    it.copy(
                        ending = false,
                        active = null,
                        recent = listOf(ended) + it.recent,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(ending = false, error = e.message) }
            }
        }
    }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer { FocusViewModel(app, ApiHolder(app)) }
        }
    }
}

package com.buddy.app.capture

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.CaptureAction
import com.buddy.app.data.CaptureConfirm
import com.buddy.app.data.CaptureDispatchResponse
import com.buddy.app.data.CaptureRequest
import com.buddy.app.data.CaptureResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class CaptureStage {
    LISTENING,
    CONFIRMING,
    DISPATCHING,
    DONE,
    ERROR,
}

data class CaptureUiState(
    val configured: Boolean = false,
    val stage: CaptureStage = CaptureStage.LISTENING,
    val partialTranscript: String = "",
    val finalTranscript: String = "",
    val classification: CaptureResponse? = null,
    val dispatch: CaptureDispatchResponse? = null,
    val error: String? = null,
    val source: String = "manual",
)

class CaptureViewModel(holder: ApiHolder) : ViewModel() {

    private val _state = MutableStateFlow(CaptureUiState())
    val state: StateFlow<CaptureUiState> = _state.asStateFlow()

    private var api: BuddyApi? = null

    init {
        viewModelScope.launch {
            holder.apiFlow.collectLatest { value: BuddyApi? ->
                api = value
                _state.update { it.copy(configured = value != null) }
            }
        }
    }

    fun setSource(source: String) {
        _state.update { it.copy(source = source) }
    }

    fun onPartial(text: String) {
        _state.update { it.copy(partialTranscript = text) }
    }

    fun onFinal(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) {
            _state.update { it.copy(stage = CaptureStage.ERROR, error = "Didn't catch that.") }
            return
        }
        _state.update {
            it.copy(
                finalTranscript = trimmed,
                partialTranscript = "",
                stage = CaptureStage.DISPATCHING,
                error = null,
            )
        }
        classify(trimmed)
    }

    fun onVoiceError(msg: String) {
        _state.update { it.copy(stage = CaptureStage.ERROR, error = msg) }
    }

    fun submitTyped(text: String) {
        onFinal(text)
    }

    private fun classify(text: String) {
        val a = api ?: run {
            _state.update {
                it.copy(stage = CaptureStage.ERROR, error = "Backend not configured.")
            }
            return
        }
        viewModelScope.launch {
            try {
                val resp = a.capture(CaptureRequest(text = text, source = _state.value.source))
                _state.update {
                    it.copy(
                        stage = CaptureStage.CONFIRMING,
                        classification = resp,
                        error = null,
                    )
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(stage = CaptureStage.ERROR, error = e.message ?: "Capture failed")
                }
            }
        }
    }

    fun confirm(selectedActions: List<CaptureAction>) {
        val a = api ?: return
        val captureId = _state.value.classification?.captureId ?: return
        if (selectedActions.isEmpty()) {
            _state.update { it.copy(stage = CaptureStage.DONE, dispatch = null) }
            return
        }
        _state.update { it.copy(stage = CaptureStage.DISPATCHING, error = null) }
        viewModelScope.launch {
            try {
                val resp = a.captureConfirm(
                    CaptureConfirm(captureId = captureId, actions = selectedActions)
                )
                _state.update { it.copy(stage = CaptureStage.DONE, dispatch = resp) }
            } catch (e: Exception) {
                _state.update {
                    it.copy(stage = CaptureStage.ERROR, error = e.message ?: "Dispatch failed")
                }
            }
        }
    }

    fun reset() {
        _state.update {
            it.copy(
                stage = CaptureStage.LISTENING,
                partialTranscript = "",
                finalTranscript = "",
                classification = null,
                dispatch = null,
                error = null,
            )
        }
    }

    fun dismissError() {
        _state.update { it.copy(error = null) }
    }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer { CaptureViewModel(ApiHolder(app)) }
        }
    }
}

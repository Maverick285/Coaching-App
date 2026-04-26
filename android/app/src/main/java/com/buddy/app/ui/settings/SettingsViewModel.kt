package com.buddy.app.ui.settings

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiClient
import com.buddy.app.data.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val backendUrl: String = "",
    val authToken: String = "",
    val testing: Boolean = false,
    val statusMessage: String? = null,
    val isError: Boolean = false,
    val saved: Boolean = false,
)

class SettingsViewModel(
    private val settings: SettingsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val current = settings.flow.first()
            _state.update {
                it.copy(
                    backendUrl = current.backendUrl,
                    authToken = current.authToken,
                )
            }
        }
    }

    fun onBackendUrlChanged(value: String) {
        _state.update { it.copy(backendUrl = value, saved = false, statusMessage = null) }
    }

    fun onAuthTokenChanged(value: String) {
        _state.update { it.copy(authToken = value, saved = false, statusMessage = null) }
    }

    fun save() {
        viewModelScope.launch {
            settings.setBackend(_state.value.backendUrl, _state.value.authToken)
            _state.update { it.copy(saved = true) }
        }
    }

    fun testConnection(formatOk: (String) -> String, formatErr: (String) -> String) {
        val s = _state.value
        viewModelScope.launch {
            _state.update { it.copy(testing = true, statusMessage = null, isError = false) }
            // Save first so the chat screen sees the new values immediately if connection works.
            settings.setBackend(s.backendUrl, s.authToken)
            val api = ApiClient.build(s.backendUrl, s.authToken)
            if (api == null) {
                _state.update {
                    it.copy(
                        testing = false,
                        statusMessage = formatErr("URL or token is blank"),
                        isError = true,
                    )
                }
                return@launch
            }
            try {
                val health = api.health()
                _state.update {
                    it.copy(
                        testing = false,
                        statusMessage = formatOk(health.modelsResolved.values.joinToString()),
                        isError = false,
                        saved = true,
                    )
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        testing = false,
                        statusMessage = formatErr(e.message ?: "Unknown error"),
                        isError = true,
                    )
                }
            }
        }
    }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer {
                SettingsViewModel(SettingsRepository(app))
            }
        }
    }
}

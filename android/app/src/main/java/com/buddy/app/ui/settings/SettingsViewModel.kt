package com.buddy.app.ui.settings

import android.app.Application
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiClient
import com.buddy.app.data.SettingsRepository
import com.buddy.app.notifications.AlarmScheduler
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val backendUrl: String = "",
    val authToken: String = "",
    val morningHour: Int = 7,
    val morningMinute: Int = 0,
    val endOfDayHour: Int = 21,
    val endOfDayMinute: Int = 0,
    val alarmsEnabled: Boolean = true,
    val testing: Boolean = false,
    val statusMessage: String? = null,
    val isError: Boolean = false,
    val saved: Boolean = false,
)

class SettingsViewModel(
    private val app: Application,
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
                    morningHour = current.morningHour,
                    morningMinute = current.morningMinute,
                    endOfDayHour = current.endOfDayHour,
                    endOfDayMinute = current.endOfDayMinute,
                    alarmsEnabled = current.alarmsEnabled,
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

    fun setMorning(hour: Int, minute: Int) {
        _state.update {
            it.copy(morningHour = hour.coerceIn(0, 23), morningMinute = minute.coerceIn(0, 59), saved = false)
        }
    }

    fun setEndOfDay(hour: Int, minute: Int) {
        _state.update {
            it.copy(endOfDayHour = hour.coerceIn(0, 23), endOfDayMinute = minute.coerceIn(0, 59), saved = false)
        }
    }

    fun setAlarmsEnabled(enabled: Boolean) {
        _state.update { it.copy(alarmsEnabled = enabled, saved = false) }
    }

    fun save() {
        val s = _state.value
        viewModelScope.launch {
            settings.setBackend(s.backendUrl, s.authToken)
            settings.setMorning(s.morningHour, s.morningMinute)
            settings.setEndOfDay(s.endOfDayHour, s.endOfDayMinute)
            settings.setAlarmsEnabled(s.alarmsEnabled)
            applyAlarms()
            _state.update { it.copy(saved = true) }
        }
    }

    private suspend fun applyAlarms() {
        val current = settings.flow.first()
        if (current.alarmsEnabled) {
            AlarmScheduler.scheduleAll(app.applicationContext as Context, current)
        } else {
            AlarmScheduler.cancelAll(app.applicationContext as Context)
        }
    }

    fun testConnection(formatOk: (String) -> String, formatErr: (String) -> String) {
        val s = _state.value
        viewModelScope.launch {
            _state.update { it.copy(testing = true, statusMessage = null, isError = false) }
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
                // If the server has rhythm config and the local user hasn't customized,
                // accept the server defaults.
                health.dailyRhythm?.let { rhythm ->
                    _state.update {
                        it.copy(
                            morningHour = rhythm.morningHour,
                            morningMinute = rhythm.morningMinute,
                            endOfDayHour = rhythm.endOfDayHour,
                            endOfDayMinute = rhythm.endOfDayMinute,
                        )
                    }
                }
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
                SettingsViewModel(app, SettingsRepository(app))
            }
        }
    }
}

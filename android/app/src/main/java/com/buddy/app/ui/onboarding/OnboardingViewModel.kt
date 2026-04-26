package com.buddy.app.ui.onboarding

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiClient
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.GoalCreate
import com.buddy.app.data.IntakeFinalizeRequest
import com.buddy.app.data.IntakeTurnRequest
import com.buddy.app.data.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Drives the first-run onboarding flow:
 *
 *   STEP 0 — Welcome (single screen, "Let's set this up")
 *   STEP 1 — Backend URL + token + Test Connection
 *   STEP 2 — Persona intake (10 questions, conversational; skippable)
 *   STEP 3 — Daily rhythm (morning + EOD times, ask for notification perm)
 *   STEP 4 — First goal (optional quick-add)
 *   STEP 5 — Done (summary + dismiss)
 *
 * Every step except WELCOME and DONE is skippable. Skipping the intake
 * leaves the persona at "Coach" defaults — the user can re-run from
 * Settings → Re-run intake.
 */
enum class OnboardingStep {
    WELCOME, BACKEND, INTAKE, RHYTHM, FIRST_GOAL, DONE
}

data class OnboardingUiState(
    val step: OnboardingStep = OnboardingStep.WELCOME,
    // Backend step
    val backendUrl: String = "",
    val authToken: String = "",
    val testing: Boolean = false,
    val testResult: String? = null,
    val testError: Boolean = false,
    val backendValidated: Boolean = false,
    // Intake step
    val intakeId: String? = null,
    val intakeQuestion: String? = null,
    val intakeStep: Int = 0,
    val intakeTotal: Int = 0,
    val intakeAnswer: String = "",
    val intakeSubmitting: Boolean = false,
    val intakeFinalizing: Boolean = false,
    val intakeFinished: Boolean = false,
    // Rhythm step
    val morningHour: Int = 7,
    val morningMinute: Int = 0,
    val eodHour: Int = 21,
    val eodMinute: Int = 0,
    val alarmsEnabled: Boolean = true,
    // First goal step
    val firstGoalStatement: String = "",
    val firstGoalUnit: String = "",
    val firstGoalAmount: String = "",
    val creatingGoal: Boolean = false,
    val firstGoalId: Int? = null,
    val error: String? = null,
)

class OnboardingViewModel(
    application: Application,
    private val settingsRepo: SettingsRepository,
    private val holder: ApiHolder,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(OnboardingUiState())
    val state: StateFlow<OnboardingUiState> = _state.asStateFlow()

    private var api: BuddyApi? = null

    init {
        viewModelScope.launch {
            // Seed from existing settings.
            settingsRepo.flow.collect { s ->
                _state.update {
                    it.copy(
                        backendUrl = if (it.backendUrl.isEmpty()) s.backendUrl else it.backendUrl,
                        authToken = if (it.authToken.isEmpty()) s.authToken else it.authToken,
                        morningHour = s.morningHour,
                        morningMinute = s.morningMinute,
                        eodHour = s.endOfDayHour,
                        eodMinute = s.endOfDayMinute,
                        alarmsEnabled = s.alarmsEnabled,
                    )
                }
            }
        }
        viewModelScope.launch {
            holder.apiFlow.collectLatest { value: BuddyApi? -> api = value }
        }
    }

    // ---- Navigation ----------------------------------------------------

    fun next() {
        val s = _state.value
        val nextStep = when (s.step) {
            OnboardingStep.WELCOME -> OnboardingStep.BACKEND
            OnboardingStep.BACKEND -> OnboardingStep.INTAKE
            OnboardingStep.INTAKE -> OnboardingStep.RHYTHM
            OnboardingStep.RHYTHM -> OnboardingStep.FIRST_GOAL
            OnboardingStep.FIRST_GOAL -> OnboardingStep.DONE
            OnboardingStep.DONE -> OnboardingStep.DONE
        }
        _state.update { it.copy(step = nextStep, error = null) }
    }

    fun back() {
        val s = _state.value
        val prev = when (s.step) {
            OnboardingStep.WELCOME -> OnboardingStep.WELCOME
            OnboardingStep.BACKEND -> OnboardingStep.WELCOME
            OnboardingStep.INTAKE -> OnboardingStep.BACKEND
            OnboardingStep.RHYTHM -> OnboardingStep.INTAKE
            OnboardingStep.FIRST_GOAL -> OnboardingStep.RHYTHM
            OnboardingStep.DONE -> OnboardingStep.FIRST_GOAL
        }
        _state.update { it.copy(step = prev, error = null) }
    }

    fun finish(onComplete: () -> Unit) {
        viewModelScope.launch {
            settingsRepo.setOnboardingComplete(true)
            onComplete()
        }
    }

    fun onClearError() = _state.update { it.copy(error = null) }

    // ---- Backend step --------------------------------------------------

    fun setBackendUrl(value: String) {
        _state.update { it.copy(backendUrl = value, backendValidated = false, testResult = null) }
    }

    fun setAuthToken(value: String) {
        _state.update { it.copy(authToken = value, backendValidated = false, testResult = null) }
    }

    fun testBackend() {
        val s = _state.value
        viewModelScope.launch {
            _state.update { it.copy(testing = true, testResult = null, testError = false) }
            val client = ApiClient.build(s.backendUrl, s.authToken)
            if (client == null) {
                _state.update {
                    it.copy(
                        testing = false,
                        testResult = "URL or token is blank.",
                        testError = true,
                    )
                }
                return@launch
            }
            try {
                val health = client.health()
                settingsRepo.setBackend(s.backendUrl, s.authToken)
                health.dailyRhythm?.let { rhythm ->
                    _state.update {
                        it.copy(
                            morningHour = rhythm.morningHour,
                            morningMinute = rhythm.morningMinute,
                            eodHour = rhythm.endOfDayHour,
                            eodMinute = rhythm.endOfDayMinute,
                        )
                    }
                }
                _state.update {
                    it.copy(
                        testing = false,
                        testResult = "Connected · models: ${health.modelsResolved.values.joinToString()}",
                        testError = false,
                        backendValidated = true,
                    )
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        testing = false,
                        testResult = e.message ?: "Connection failed",
                        testError = true,
                        backendValidated = false,
                    )
                }
            }
        }
    }

    // ---- Intake step ---------------------------------------------------

    fun startIntake() {
        val a = api ?: return
        viewModelScope.launch {
            _state.update { it.copy(intakeSubmitting = true, error = null) }
            try {
                val resp = a.intakeStart()
                _state.update {
                    it.copy(
                        intakeSubmitting = false,
                        intakeId = resp.intakeId,
                        intakeQuestion = resp.question,
                        intakeStep = resp.step,
                        intakeTotal = resp.totalSteps,
                        intakeAnswer = "",
                        intakeFinished = false,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(intakeSubmitting = false, error = e.message) }
            }
        }
    }

    fun setIntakeAnswer(value: String) {
        _state.update { it.copy(intakeAnswer = value) }
    }

    fun submitIntakeAnswer() {
        val a = api ?: return
        val s = _state.value
        val intakeId = s.intakeId ?: return
        if (s.intakeAnswer.isBlank()) return
        viewModelScope.launch {
            _state.update { it.copy(intakeSubmitting = true, error = null) }
            try {
                val resp = a.intakeTurn(IntakeTurnRequest(intakeId, s.intakeAnswer.trim()))
                _state.update {
                    it.copy(
                        intakeSubmitting = false,
                        intakeQuestion = resp.question,
                        intakeStep = resp.step,
                        intakeAnswer = "",
                        intakeFinished = resp.finished,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(intakeSubmitting = false, error = e.message) }
            }
        }
    }

    fun finalizeIntake() {
        val a = api ?: return
        val intakeId = _state.value.intakeId ?: return
        viewModelScope.launch {
            _state.update { it.copy(intakeFinalizing = true, error = null) }
            try {
                a.intakeFinalize(IntakeFinalizeRequest(intakeId))
                _state.update { it.copy(intakeFinalizing = false) }
                next()
            } catch (e: Exception) {
                _state.update { it.copy(intakeFinalizing = false, error = e.message) }
            }
        }
    }

    fun skipIntake() {
        _state.update { it.copy(intakeId = null, intakeQuestion = null, intakeFinished = false) }
        next()
    }

    // ---- Rhythm step ---------------------------------------------------

    fun setMorning(hour: Int, minute: Int) {
        _state.update {
            it.copy(morningHour = hour.coerceIn(0, 23), morningMinute = minute.coerceIn(0, 59))
        }
    }

    fun setEod(hour: Int, minute: Int) {
        _state.update {
            it.copy(eodHour = hour.coerceIn(0, 23), eodMinute = minute.coerceIn(0, 59))
        }
    }

    fun setAlarmsEnabled(enabled: Boolean) {
        _state.update { it.copy(alarmsEnabled = enabled) }
    }

    fun saveRhythmAndContinue() {
        val s = _state.value
        viewModelScope.launch {
            settingsRepo.setMorning(s.morningHour, s.morningMinute)
            settingsRepo.setEndOfDay(s.eodHour, s.eodMinute)
            settingsRepo.setAlarmsEnabled(s.alarmsEnabled)
            next()
        }
    }

    // ---- First goal step ----------------------------------------------

    fun setFirstGoalStatement(value: String) =
        _state.update { it.copy(firstGoalStatement = value) }

    fun setFirstGoalUnit(value: String) =
        _state.update { it.copy(firstGoalUnit = value) }

    fun setFirstGoalAmount(value: String) =
        _state.update { it.copy(firstGoalAmount = value) }

    fun createFirstGoalAndContinue() {
        val a = api ?: return next()
        val s = _state.value
        if (s.firstGoalStatement.isBlank()) {
            next()
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(creatingGoal = true, error = null) }
            try {
                val g = a.createGoal(
                    GoalCreate(
                        statement = s.firstGoalStatement.trim(),
                        priority = 4,
                        paceTargetUnit = s.firstGoalUnit.trim(),
                        paceTargetAmount = s.firstGoalAmount.toDoubleOrNull() ?: 0.0,
                    )
                )
                _state.update { it.copy(creatingGoal = false, firstGoalId = g.id) }
                next()
            } catch (e: Exception) {
                _state.update { it.copy(creatingGoal = false, error = e.message) }
            }
        }
    }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer {
                OnboardingViewModel(app, SettingsRepository(app), ApiHolder(app))
            }
        }
    }
}

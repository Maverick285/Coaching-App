package com.buddy.app.ui.today

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.DayGrade
import com.buddy.app.data.FocusSession
import com.buddy.app.data.Goal
import com.buddy.app.data.StreakResponse
import com.buddy.app.data.Task
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Home/Today screen state per master spec §23.2 + §27.1.
 *
 * The screen is context-aware — its primary card adapts to whatever
 * mode the user is in (active session / EOD pending / today's tasks /
 * empty). Backend returns the inputs; this VM resolves which mode
 * applies and exposes a flat state for the screen to render.
 */

enum class TodayMode {
    LOADING,
    ACTIVE_SESSION,
    EOD_PENDING,
    HAS_TASKS,
    EMPTY,
    NOT_CONFIGURED,
}

data class TodayUiState(
    val mode: TodayMode = TodayMode.LOADING,
    val grade: DayGrade? = null,
    val streak: StreakResponse? = null,
    val activeSession: FocusSession? = null,
    val activeGoals: List<Goal> = emptyList(),
    val openTasks: List<Task> = emptyList(),
    val goalsById: Map<Int, Goal> = emptyMap(),
    val pendingDreams: Int = 0,
    val error: String? = null,
)

class TodayViewModel(holder: ApiHolder) : ViewModel() {
    private val _state = MutableStateFlow(TodayUiState())
    val state: StateFlow<TodayUiState> = _state.asStateFlow()

    private var api: BuddyApi? = null

    init {
        viewModelScope.launch {
            holder.apiFlow.collectLatest { value ->
                api = value
                if (value == null) {
                    _state.update { it.copy(mode = TodayMode.NOT_CONFIGURED) }
                } else {
                    refresh()
                }
            }
        }
    }

    fun refresh() {
        val a = api ?: return
        viewModelScope.launch {
            try {
                // Fan-out: each call is independent; if any fail
                // individually we still render what we have.
                val grade = runCatching { a.gradeToday() }.getOrNull()
                val streak = runCatching { a.streak(30) }.getOrNull()
                val active = runCatching { a.activeFocus().session }.getOrNull()
                val goals = runCatching { a.listGoals(state = "active").goals }.getOrDefault(emptyList())
                val tasks = runCatching {
                    a.listTasks().tasks.filter { it.state != "done" && it.state != "skipped" }
                }.getOrDefault(emptyList())
                val dreams = runCatching { a.dreams().pending.size }.getOrDefault(0)

                val mode = when {
                    active != null -> TodayMode.ACTIVE_SESSION
                    grade?.finalized == false && (grade.systemScore > 0.0 || tasks.isEmpty().not()) ->
                        // Day has scored progress but isn't finalized yet — EOD prompt could fire
                        if (_isEodWindow()) TodayMode.EOD_PENDING else TodayMode.HAS_TASKS
                    tasks.isNotEmpty() -> TodayMode.HAS_TASKS
                    else -> TodayMode.EMPTY
                }

                _state.update {
                    it.copy(
                        mode = mode,
                        grade = grade,
                        streak = streak,
                        activeSession = active,
                        activeGoals = goals,
                        openTasks = tasks,
                        goalsById = goals.associateBy { g -> g.id },
                        pendingDreams = dreams,
                        error = null,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun toggleTaskDone(task: Task) {
        val a = api ?: return
        viewModelScope.launch {
            try {
                val newState = if (task.state == "done") "proposed" else "done"
                a.updateTask(task.id, com.buddy.app.data.TaskUpdate(state = newState))
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun onClearError() = _state.update { it.copy(error = null) }

    private fun _isEodWindow(): Boolean {
        // Treat 17:00..23:59 local as the EOD window. Real boundary
        // detection lives on the backend (BUDDY_END_OF_DAY_*); the
        // screen mode is just a display heuristic.
        val hour = java.time.LocalTime.now().hour
        return hour >= 17
    }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer { TodayViewModel(ApiHolder(app)) }
        }
    }
}

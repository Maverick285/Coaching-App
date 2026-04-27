package com.buddy.app.ui.tasks

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.Goal
import com.buddy.app.data.Task
import com.buddy.app.data.TaskBatchNLRequest
import com.buddy.app.data.TaskCreate
import com.buddy.app.data.TaskUpdate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class TasksUiState(
    val configured: Boolean = false,
    val loading: Boolean = false,
    val tasks: List<Task> = emptyList(),
    val goalsById: Map<Int, Goal> = emptyMap(),
    val nlText: String = "",
    val nlRunning: Boolean = false,
    val info: String? = null,
    val error: String? = null,
)

class TasksViewModel(holder: ApiHolder) : ViewModel() {
    private val _state = MutableStateFlow(TasksUiState())
    val state: StateFlow<TasksUiState> = _state.asStateFlow()

    private var api: BuddyApi? = null

    init {
        viewModelScope.launch {
            holder.apiFlow.collectLatest { value ->
                api = value
                _state.update { it.copy(configured = value != null) }
                if (value != null) refresh()
            }
        }
    }

    fun refresh() {
        val a = api ?: return
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val goals = a.listGoals().goals.associateBy { it.id }
                val tasks = a.listTasks().tasks
                _state.update {
                    it.copy(
                        loading = false,
                        tasks = tasks,
                        goalsById = goals,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    fun setNlText(value: String) = _state.update { it.copy(nlText = value) }
    fun onClearError() = _state.update { it.copy(error = null) }
    fun onClearInfo() = _state.update { it.copy(info = null) }

    fun toggleDone(task: Task) {
        val a = api ?: return
        viewModelScope.launch {
            try {
                val newState = if (task.state == "done") "proposed" else "done"
                a.updateTask(task.id, TaskUpdate(state = newState))
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun deleteTask(id: Int) {
        val a = api ?: return
        viewModelScope.launch {
            try {
                a.deleteTask(id)
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun editTask(id: Int, description: String, durationMinutes: Int?) {
        val a = api ?: return
        viewModelScope.launch {
            try {
                a.updateTask(
                    id,
                    TaskUpdate(
                        description = description.trim(),
                        estimatedDurationMinutes = durationMinutes,
                    ),
                )
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun createSimple(goalId: Int, description: String) {
        val a = api ?: return
        viewModelScope.launch {
            try {
                a.createTask(TaskCreate(goalId = goalId, description = description.trim()))
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun runNlBatch(source: String = "text") {
        val a = api ?: return
        val text = _state.value.nlText.trim()
        if (text.isEmpty() || _state.value.nlRunning) return
        _state.update { it.copy(nlRunning = true, error = null) }
        viewModelScope.launch {
            try {
                val resp = a.tasksBatchNL(TaskBatchNLRequest(text = text, source = source))
                val ok = resp.results.count { it.status == "ok" }
                val fail = resp.results.size - ok
                val msg = when {
                    resp.results.isEmpty() -> "Nothing actionable found."
                    fail == 0 -> "Applied $ok change${if (ok == 1) "" else "s"}."
                    else -> "$ok ok, $fail failed."
                }
                _state.update {
                    it.copy(nlRunning = false, nlText = "", info = msg)
                }
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(nlRunning = false, error = e.message) }
            }
        }
    }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer { TasksViewModel(ApiHolder(app)) }
        }
    }
}

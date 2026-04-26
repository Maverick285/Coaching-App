package com.buddy.app.ui.goals

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.Goal
import com.buddy.app.data.GoalCreate
import com.buddy.app.data.GoalDetail
import com.buddy.app.data.GoalUpdate
import com.buddy.app.data.ProductivityRepository
import com.buddy.app.data.ProgressLogCreate
import com.buddy.app.data.TaskCreate
import com.buddy.app.data.WoopRequest
import com.buddy.app.data.WoopResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class GoalsUiState(
    val configured: Boolean = false,
    val loading: Boolean = false,
    val goals: List<Goal> = emptyList(),
    val error: String? = null,
)

class GoalsViewModel(holder: ApiHolder) : ViewModel() {

    private val _state = MutableStateFlow(GoalsUiState())
    val state: StateFlow<GoalsUiState> = _state.asStateFlow()

    private var repo: ProductivityRepository? = null

    init {
        viewModelScope.launch {
            holder.apiFlow.collectLatest { api: BuddyApi? ->
                repo = api?.let { ProductivityRepository(it) }
                _state.update { it.copy(configured = api != null) }
                if (api != null) refresh()
            }
        }
    }

    fun refresh() {
        val r = repo ?: return
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val data = r.listGoals()
                _state.update { it.copy(loading = false, goals = data.goals) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    fun onClearError() {
        _state.update { it.copy(error = null) }
    }

    fun createGoal(req: GoalCreate, onDone: (Goal) -> Unit = {}) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                val g = r.createGoal(req)
                _state.update { it.copy(goals = listOf(g) + it.goals) }
                onDone(g)
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun updateGoalState(id: Int, newState: String) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                val updated = r.updateGoal(id, GoalUpdate(state = newState))
                _state.update { st ->
                    st.copy(goals = st.goals.map { if (it.id == updated.id) updated else it })
                }
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun runWoop(req: WoopRequest, onDone: (WoopResponse) -> Unit) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                onDone(r.runWoop(req))
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer { GoalsViewModel(ApiHolder(app)) }
        }
    }
}


// --- Goal detail VM --------------------------------------------------------

data class GoalDetailUiState(
    val configured: Boolean = false,
    val loading: Boolean = false,
    val detail: GoalDetail? = null,
    val distractionRules: List<com.buddy.app.data.DistractionRule> = emptyList(),
    val blockedApps: List<com.buddy.app.data.BlockedAppRule> = emptyList(),
    val error: String? = null,
)

class GoalDetailViewModel(
    private val goalId: Int,
    holder: ApiHolder,
) : ViewModel() {

    private val _state = MutableStateFlow(GoalDetailUiState())
    val state: StateFlow<GoalDetailUiState> = _state.asStateFlow()

    private var repo: ProductivityRepository? = null

    init {
        viewModelScope.launch {
            holder.apiFlow.collectLatest { api: BuddyApi? ->
                repo = api?.let { ProductivityRepository(it) }
                _state.update { it.copy(configured = api != null) }
                if (api != null) refresh()
            }
        }
    }

    fun refresh() {
        val r = repo ?: return
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val detail = r.getGoal(goalId)
                val rules = try {
                    r.api.distractionRules(goalId).rules
                } catch (_: Exception) {
                    emptyList()
                }
                val blocks = try {
                    r.api.blockedApps(goalId).rules
                } catch (_: Exception) {
                    emptyList()
                }
                _state.update {
                    it.copy(
                        loading = false,
                        detail = detail,
                        distractionRules = rules,
                        blockedApps = blocks,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    fun addDistractionRule(category: String, cooldownSeconds: Int = 90) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                r.api.createDistractionRule(
                    com.buddy.app.data.DistractionRuleCreate(
                        goalId = goalId,
                        distractorCategory = category,
                        cooldownSeconds = cooldownSeconds,
                    )
                )
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun removeDistractionRule(id: Int) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                r.api.deleteDistractionRule(id)
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun addBlockedApp(packageName: String, blockTier: Int) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                r.api.createBlockedApp(
                    com.buddy.app.data.BlockedAppRuleCreate(
                        goalId = goalId,
                        packageName = packageName,
                        blockTier = blockTier,
                    )
                )
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun removeBlockedApp(id: Int) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                r.api.deleteBlockedApp(id)
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun logProgress(units: Double, unitLabel: String, rawText: String = "") {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                r.logProgress(
                    ProgressLogCreate(
                        goalId = goalId,
                        attributedUnits = units,
                        unitLabel = unitLabel,
                        rawText = rawText,
                    )
                )
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun addTask(description: String, durationMinutes: Int? = null, first60: String = "") {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                r.createTask(
                    TaskCreate(
                        goalId = goalId,
                        description = description,
                        estimatedDurationMinutes = durationMinutes,
                        first60Seconds = first60,
                    )
                )
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun setTaskDone(taskId: Int) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                r.updateTask(taskId, com.buddy.app.data.TaskUpdate(state = "done"))
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun onClearError() {
        _state.update { it.copy(error = null) }
    }

    companion object {
        fun factory(app: Application, goalId: Int): ViewModelProvider.Factory =
            viewModelFactory {
                initializer { GoalDetailViewModel(goalId, ApiHolder(app)) }
            }
    }
}

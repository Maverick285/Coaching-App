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
import com.buddy.app.data.GoalPlan
import com.buddy.app.data.GoalPlanApplyRequest
import com.buddy.app.data.GoalPlanRequest
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
    val goals: List<Goal> = emptyList(),  // active only by default
    val activeCount: Int = 0,
    val backlogCount: Int = 0,
    val error: String? = null,
    val limitHit: LimitHitInfo? = null,
    // One-shot navigation event. The screen consumes this in a
    // LaunchedEffect and clears it; we use it both for the simple
    // happy-path create and for the pause-and-retry continuation
    // (otherwise the user pauses a goal but never gets navigated to
    // the new one).
    val justCreatedGoalId: Int? = null,
    val justStashed: Boolean = false,
)

data class LimitHitInfo(
    val message: String,
    val pendingRequest: GoalCreate,
    val pendingPlan: GoalPlan? = null,  // present if it was a plan-apply
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
                val active = r.listGoals(state = "active").goals
                    .filter { it.parentGoalId == null }
                val all = r.listGoals().goals
                val backlogCount = all.count { g ->
                    g.parentGoalId == null && g.state in setOf("paused", "completed", "abandoned")
                }
                _state.update {
                    it.copy(
                        loading = false,
                        goals = active,
                        activeCount = active.size,
                        backlogCount = backlogCount,
                    )
                }
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
                _state.update {
                    it.copy(
                        goals = if (g.state == "active") listOf(g) + it.goals else it.goals,
                        activeCount = it.activeCount + (if (g.state == "active") 1 else 0),
                        backlogCount = it.backlogCount + (if (g.state != "active") 1 else 0),
                        justCreatedGoalId = if (g.state == "active") g.id else null,
                        justStashed = g.state != "active",
                    )
                }
                onDone(g)
            } catch (e: retrofit2.HttpException) {
                if (e.code() == 409) {
                    _state.update {
                        it.copy(
                            limitHit = LimitHitInfo(
                                message = parseLimitMessage(e),
                                pendingRequest = req,
                            )
                        )
                    }
                } else {
                    _state.update { it.copy(error = e.message) }
                }
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

    fun planGoal(
        wish: String,
        deadline: String?,
        onDone: (GoalPlan) -> Unit,
        onError: (String) -> Unit,
    ) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                val resp = r.api.planGoal(GoalPlanRequest(wish = wish.trim(), deadline = deadline))
                onDone(resp.plan)
            } catch (e: Exception) {
                onError(e.message ?: "Failed to plan goal")
            }
        }
    }

    fun applyPlan(plan: GoalPlan, onDone: (Int) -> Unit = {}) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                val resp = r.api.applyGoalPlan(GoalPlanApplyRequest(plan = plan))
                refresh()
                _state.update { it.copy(justCreatedGoalId = resp.goalId) }
                onDone(resp.goalId)
            } catch (e: retrofit2.HttpException) {
                if (e.code() == 409) {
                    _state.update {
                        it.copy(
                            limitHit = LimitHitInfo(
                                message = parseLimitMessage(e),
                                pendingRequest = GoalCreate(statement = plan.statement),
                                pendingPlan = plan,
                            )
                        )
                    }
                } else {
                    _state.update { it.copy(error = e.message) }
                }
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun pauseGoalAndRetry(goalIdToPause: Int) {
        val r = repo ?: return
        val pending = _state.value.limitHit ?: return
        viewModelScope.launch {
            try {
                r.updateGoal(goalIdToPause, GoalUpdate(state = "paused"))
                _state.update { it.copy(limitHit = null) }
                // The retry below sets justCreatedGoalId on success;
                // the screen's LaunchedEffect navigates from there.
                if (pending.pendingPlan != null) {
                    applyPlan(pending.pendingPlan)
                } else {
                    createGoal(pending.pendingRequest)
                }
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun stashAsBacklog() {
        val r = repo ?: return
        val pending = _state.value.limitHit ?: return
        viewModelScope.launch {
            try {
                // Server now accepts state=paused on initial create, so
                // this is a single round-trip without tripping the cap.
                val g = r.createGoal(pending.pendingRequest.copy(state = "paused"))
                _state.update {
                    it.copy(
                        limitHit = null,
                        backlogCount = it.backlogCount + 1,
                        justStashed = true,
                    )
                }
                refresh()
                // Suppress unused-variable warning; g is the receipt.
                @Suppress("UNUSED_VARIABLE") val _g = g
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun consumeJustCreated() = _state.update {
        it.copy(justCreatedGoalId = null, justStashed = false)
    }

    fun cancelLimitHit() = _state.update { it.copy(limitHit = null) }

    private fun parseLimitMessage(e: retrofit2.HttpException): String {
        return runCatching {
            val body = e.response()?.errorBody()?.string().orEmpty()
            // Server returns: {"error":"http_error","detail":{"message": "..."}}
            kotlinx.serialization.json.Json
                .parseToJsonElement(body)
                .let { it as? kotlinx.serialization.json.JsonObject }
                ?.get("detail")
                ?.let { it as? kotlinx.serialization.json.JsonObject }
                ?.get("message")
                ?.toString()?.trim('"')
        }.getOrNull() ?: "You have 4 active goals already."
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

    fun updateGoal(update: com.buddy.app.data.GoalUpdate, onDone: () -> Unit = {}) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                r.updateGoal(goalId, update)
                refresh()
                onDone()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun deleteGoal(onDone: () -> Unit) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                r.api.deleteGoal(goalId)
                onDone()
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

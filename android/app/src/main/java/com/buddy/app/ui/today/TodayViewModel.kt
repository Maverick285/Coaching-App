package com.buddy.app.ui.today

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.DailyPlan
import com.buddy.app.data.DailyPlanItem
import com.buddy.app.data.DailyPlanItemActionRequest
import com.buddy.app.data.DayGrade
import com.buddy.app.data.FocusSession
import com.buddy.app.data.Goal
import com.buddy.app.data.StreakResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Today screen state. The screen is now plan-first: on first morning
 * use of a new day, the backend generates today's plan (a list of
 * goal-derived tasks tiered must/should/could), and we render it as
 * the primary content. Day grade + streak are still shown at the top
 * for context. The old "next action card" + open-tasks list is
 * retired in favor of swipeable plan items.
 */
data class TodayUiState(
    val configured: Boolean = true,
    val loading: Boolean = false,
    val plan: DailyPlan? = null,
    val grade: DayGrade? = null,
    val streak: StreakResponse? = null,
    val activeSession: FocusSession? = null,
    val goalsById: Map<Int, Goal> = emptyMap(),
    val pendingDreams: Int = 0,
    val savingItemIds: Set<Int> = emptySet(),
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
                    _state.update { it.copy(configured = false, loading = false) }
                } else {
                    _state.update { it.copy(configured = true) }
                    refresh()
                }
            }
        }
    }

    fun refresh() {
        val a = api ?: return
        viewModelScope.launch {
            _state.update { it.copy(loading = true) }
            try {
                val plan = runCatching { a.dailyPlanToday() }.getOrNull()
                val grade = runCatching { a.gradeToday() }.getOrNull()
                val streak = runCatching { a.streak(30) }.getOrNull()
                val active = runCatching { a.activeFocus().session }.getOrNull()
                val goals = runCatching {
                    a.listGoals(state = "active").goals
                }.getOrDefault(emptyList())
                val dreams = runCatching { a.dreams().pending.size }.getOrDefault(0)

                _state.update {
                    it.copy(
                        loading = false,
                        plan = plan,
                        grade = grade,
                        streak = streak,
                        activeSession = active,
                        goalsById = goals.associateBy { g -> g.id },
                        pendingDreams = dreams,
                        error = null,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    fun markDone(item: DailyPlanItem) = applyAction(item, "done")
    fun decline(item: DailyPlanItem) = applyAction(item, "decline")

    fun deferUntilLater(item: DailyPlanItem, reason: String? = null) {
        applyAction(item, "defer", reason)
    }

    private fun applyAction(item: DailyPlanItem, action: String, reason: String? = null) {
        val a = api ?: return
        if (item.id in _state.value.savingItemIds) return
        _state.update { it.copy(savingItemIds = it.savingItemIds + item.id) }
        viewModelScope.launch {
            try {
                val updated = a.dailyPlanAction(
                    item.id,
                    DailyPlanItemActionRequest(action = action, reason = reason),
                )
                _state.update { st ->
                    val newItems = st.plan?.items?.map { if (it.id == updated.id) updated else it }
                        ?: emptyList()
                    st.copy(
                        plan = st.plan?.copy(items = newItems),
                        savingItemIds = st.savingItemIds - item.id,
                    )
                }
                com.buddy.app.data.RefreshBus.notifyGoals()
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        savingItemIds = it.savingItemIds - item.id,
                        error = e.message ?: "Couldn't save that.",
                    )
                }
            }
        }
    }

    fun onClearError() = _state.update { it.copy(error = null) }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer { TodayViewModel(ApiHolder(app)) }
        }
    }
}

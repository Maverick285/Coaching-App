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
import com.buddy.app.data.GoalUpdate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class BacklogUiState(
    val goals: List<Goal> = emptyList(),
    val message: String? = null,
    val error: String? = null,
)

class BacklogViewModel(holder: ApiHolder) : ViewModel() {
    private val _state = MutableStateFlow(BacklogUiState())
    val state: StateFlow<BacklogUiState> = _state.asStateFlow()

    private var api: BuddyApi? = null

    init {
        viewModelScope.launch {
            holder.apiFlow.collectLatest { value ->
                api = value
                if (value != null) refresh()
            }
        }
    }

    fun refresh() {
        val a = api ?: return
        viewModelScope.launch {
            try {
                // No state filter — server returns everything; we filter
                // out active top-level + sub-goals locally. Sub-goals
                // belong with their parent, not the master list.
                val list = a.listGoals().goals.filter {
                    it.parentGoalId == null && it.state != "active"
                }
                _state.update { it.copy(goals = list) }
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun resume(goalId: Int) {
        val a = api ?: return
        viewModelScope.launch {
            try {
                a.updateGoal(goalId, GoalUpdate(state = "active"))
                _state.update { it.copy(message = "Resumed.") }
                refresh()
            } catch (e: retrofit2.HttpException) {
                if (e.code() == 409) {
                    _state.update {
                        it.copy(
                            error = "You're at 4 active goals. Pause one from the Goals tab first.",
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

    fun onClearError() = _state.update { it.copy(error = null) }
    fun onClearMessage() = _state.update { it.copy(message = null) }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer { BacklogViewModel(ApiHolder(app)) }
        }
    }
}

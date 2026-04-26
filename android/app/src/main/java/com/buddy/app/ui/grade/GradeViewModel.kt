package com.buddy.app.ui.grade

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.DayGrade
import com.buddy.app.data.DayGradeFinalize
import com.buddy.app.data.ProductivityRepository
import com.buddy.app.data.StreakResponse
import com.buddy.app.data.WeeklyReviewResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter

data class GradeUiState(
    val configured: Boolean = false,
    val loading: Boolean = false,
    val grade: DayGrade? = null,
    val streak: StreakResponse? = null,
    val weekly: WeeklyReviewResponse? = null,
    val weeklyLoading: Boolean = false,
    val error: String? = null,
)

class GradeViewModel(holder: ApiHolder) : ViewModel() {

    private val _state = MutableStateFlow(GradeUiState())
    val state: StateFlow<GradeUiState> = _state.asStateFlow()

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
                val grade = r.gradeToday()
                val streak = r.streak(30)
                _state.update { it.copy(loading = false, grade = grade, streak = streak) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    fun finalize(acceptSystem: Boolean, userScore: Double?, notes: String) {
        val r = repo ?: return
        val today = LocalDate.now().format(DateTimeFormatter.ISO_DATE)
        viewModelScope.launch {
            try {
                val updated = r.finalizeGrade(
                    today,
                    DayGradeFinalize(
                        userScore = userScore,
                        userNotes = notes,
                        acceptSystemScore = acceptSystem,
                    ),
                )
                _state.update { it.copy(grade = updated) }
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun fetchWeeklyReview() {
        val r = repo ?: return
        viewModelScope.launch {
            _state.update { it.copy(weeklyLoading = true, error = null) }
            try {
                val w = r.weeklyReview()
                _state.update { it.copy(weeklyLoading = false, weekly = w) }
            } catch (e: Exception) {
                _state.update { it.copy(weeklyLoading = false, error = e.message) }
            }
        }
    }

    fun onClearError() = _state.update { it.copy(error = null) }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer { GradeViewModel(ApiHolder(app)) }
        }
    }
}

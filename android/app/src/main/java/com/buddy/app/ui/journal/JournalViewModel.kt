package com.buddy.app.ui.journal

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.JournalEntry
import com.buddy.app.data.JournalEntryWrite
import com.buddy.app.data.ProductivityRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter

data class JournalUiState(
    val configured: Boolean = false,
    val loading: Boolean = false,
    val today: String = "",
    val content: String = "",
    val mood: String = "",
    val recent: List<JournalEntry> = emptyList(),
    val saving: Boolean = false,
    val saved: Boolean = false,
    val error: String? = null,
)

class JournalViewModel(holder: ApiHolder) : ViewModel() {

    private val _state = MutableStateFlow(
        JournalUiState(today = LocalDate.now().format(DateTimeFormatter.ISO_DATE))
    )
    val state: StateFlow<JournalUiState> = _state.asStateFlow()

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
            _state.update { it.copy(loading = true, error = null, saved = false) }
            try {
                val entry = r.getJournal(_state.value.today)
                val list = r.listJournal(20).entries
                _state.update {
                    it.copy(
                        loading = false,
                        content = entry.content,
                        mood = entry.mood,
                        recent = list,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    fun onContentChanged(value: String) {
        _state.update { it.copy(content = value, saved = false) }
    }

    fun onMoodChanged(value: String) {
        _state.update { it.copy(mood = value, saved = false) }
    }

    fun save() {
        val r = repo ?: return
        viewModelScope.launch {
            _state.update { it.copy(saving = true, error = null) }
            try {
                r.upsertJournal(
                    _state.value.today,
                    JournalEntryWrite(
                        content = _state.value.content,
                        mood = _state.value.mood,
                        tags = emptyList(),
                    ),
                )
                _state.update { it.copy(saving = false, saved = true) }
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(saving = false, error = e.message) }
            }
        }
    }

    fun onClearError() = _state.update { it.copy(error = null) }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer { JournalViewModel(ApiHolder(app)) }
        }
    }
}

package com.buddy.app.ui.dreams

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.DreamAction
import com.buddy.app.data.DreamProposal
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Dreams = consolidation pass output the user reviews each morning.
 * Per spec §35.4: pending review on top (cards with approve/reject/edit),
 * auto-applied recent collapsed below for awareness.
 */
data class DreamsUiState(
    val configured: Boolean = false,
    val loading: Boolean = false,
    val pending: List<DreamProposal> = emptyList(),
    val autoApplied: List<DreamProposal> = emptyList(),
    val message: String? = null,
    val error: String? = null,
)

class DreamsViewModel(holder: ApiHolder) : ViewModel() {
    private val _state = MutableStateFlow(DreamsUiState())
    val state: StateFlow<DreamsUiState> = _state.asStateFlow()

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
                val r = a.dreams()
                _state.update {
                    it.copy(
                        loading = false,
                        pending = r.pending,
                        autoApplied = r.autoAppliedRecent,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    fun act(proposal: DreamProposal, action: String, editedContent: String? = null) {
        val a = api ?: return
        viewModelScope.launch {
            try {
                a.dreamAction(
                    DreamAction(
                        action = action,
                        proposalId = proposal.id,
                        editedContent = editedContent,
                    )
                )
                refresh()
                _state.update {
                    it.copy(
                        message = when (action) {
                            "approve" -> "Approved."
                            "reject" -> "Rejected."
                            else -> "Saved."
                        }
                    )
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
            initializer { DreamsViewModel(ApiHolder(app)) }
        }
    }
}

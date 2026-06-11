package com.buddy.app.ui.chat

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiClient
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.BuddySettings
import com.buddy.app.data.ChatRepository
import com.buddy.app.data.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class ChatRole { USER, ASSISTANT, SYSTEM }

data class ChatMessage(
    val id: String,
    val role: ChatRole,
    val content: String,
    val modelUsed: String = "",
    // Proposals attached to an assistant turn — rendered as inline
    // cards under the message bubble. Tap save → creates the goal.
    val proposals: List<com.buddy.app.data.ProposedAction> = emptyList(),
)

data class ChatUiState(
    val backendConfigured: Boolean = false,
    val messages: List<ChatMessage> = emptyList(),
    val composerText: String = "",
    val isSending: Boolean = false,
    val isListening: Boolean = false,
    val partialTranscript: String = "",
    // Message IDs whose proposed-goal card has a save in flight. The
    // Save button on those cards renders disabled so a quick double-
    // tap can't create two duplicate goals before the first request
    // returns.
    val savingProposals: Set<String> = emptySet(),
    val error: String? = null,
    val info: String? = null,
)

class ChatViewModel(
    private val settings: SettingsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    private var api: BuddyApi? = null
    private var repo: ChatRepository? = null
    private var sessionId: String? = null

    init {
        viewModelScope.launch {
            settings.flow.collectLatest { current ->
                rebindApi(current)
            }
        }
    }

    private suspend fun rebindApi(current: BuddySettings) {
        val newApi = ApiClient.build(current.backendUrl, current.authToken)
        api = newApi
        repo = newApi?.let { ChatRepository(it) }
        sessionId = current.sessionId.takeIf { it.isNotBlank() }
        _state.update {
            it.copy(
                backendConfigured = newApi != null,
                error = null,
            )
        }
        if (newApi != null && sessionId != null) {
            loadHistory(sessionId!!)
        } else if (newApi != null) {
            _state.update { it.copy(messages = emptyList()) }
        }
    }

    private fun loadHistory(sid: String) {
        val r = repo ?: return
        viewModelScope.launch {
            try {
                val detail = r.loadHistory(sid)
                _state.update { current ->
                    current.copy(
                        messages = detail.messages.map { m ->
                            ChatMessage(
                                id = m.id,
                                role = roleFor(m.role),
                                content = m.content,
                                modelUsed = m.modelUsed,
                            )
                        },
                    )
                }
            } catch (_: Exception) {
                // Likely a stale session id (history cleared, server replaced).
                _state.update { it.copy(messages = emptyList()) }
                settings.clearSessionId()
                sessionId = null
            }
        }
    }

    fun onComposerChanged(value: String) {
        _state.update { it.copy(composerText = value) }
    }

    fun onClearError() {
        _state.update { it.copy(error = null) }
    }

    fun onClearInfo() {
        _state.update { it.copy(info = null) }
    }

    fun startNewSession() {
        viewModelScope.launch {
            settings.clearSessionId()
            sessionId = null
            _state.update {
                it.copy(
                    messages = emptyList(),
                    composerText = "",
                    error = null,
                    info = "Started a new session.",
                )
            }
        }
    }

    fun send(message: String = _state.value.composerText) {
        val r = repo ?: return
        val content = message.trim()
        if (content.isEmpty() || _state.value.isSending) return

        val pending = ChatMessage(
            id = "local-${System.currentTimeMillis()}",
            role = ChatRole.USER,
            content = content,
        )
        _state.update {
            it.copy(
                messages = it.messages + pending,
                composerText = "",
                isSending = true,
                error = null,
            )
        }

        viewModelScope.launch {
            try {
                val resp = r.send(sessionId, content)
                if (sessionId != resp.sessionId) {
                    sessionId = resp.sessionId
                    settings.setSessionId(resp.sessionId)
                }
                val assistant = ChatMessage(
                    id = resp.messageId,
                    role = ChatRole.ASSISTANT,
                    content = resp.response,
                    modelUsed = resp.modelUsed,
                    proposals = resp.proposedActions,
                )
                _state.update {
                    it.copy(
                        messages = it.messages + assistant,
                        isSending = false,
                    )
                }
                if (resp.executedActions.isNotEmpty()) {
                    // log_progress already happened server-side. Wake
                    // the data tabs so today's grade reflects it.
                    com.buddy.app.data.RefreshBus.notifyGoals()
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        isSending = false,
                        error = e.message ?: "Request failed",
                    )
                }
            }
        }
    }

    /** Save a proposed goal from the inline chat card. Replaces the
     * proposal on the message with a "saved" marker so the user
     * can't double-tap. */
    fun confirmProposeGoal(messageId: String, payload: kotlinx.serialization.json.JsonObject) {
        val a = api ?: return
        // Guard against double-tap: if a save for this proposal is
        // already running, drop the second invocation. The card UI
        // also renders disabled while in flight, but enforce here too
        // so a fast second tap during the brief click→state-update
        // window can't sneak through.
        if (messageId in _state.value.savingProposals) return
        _state.update { it.copy(savingProposals = it.savingProposals + messageId) }
        viewModelScope.launch {
            try {
                val req = com.buddy.app.data.GoalCreate(
                    statement = payload["statement"]?.toString()?.trim('"').orEmpty(),
                    priority = payload["priority"]?.toString()?.toIntOrNull() ?: 3,
                    paceTargetAmount = payload["pace_target_amount"]?.toString()?.toDoubleOrNull() ?: 0.0,
                    paceTargetUnit = payload["pace_target_unit"]?.toString()?.trim('"').orEmpty(),
                    mvpThreshold = payload["mvp_threshold"]?.toString()?.trim('"').orEmpty(),
                    deadline = payload["deadline"]?.toString()?.trim('"')
                        ?.takeIf { it.isNotEmpty() && it != "null" },
                    timeframe = (payload["deadline"]?.toString()?.trim('"').orEmpty())
                        .let { if (it.isNotEmpty() && it != "null") "deadline" else "open_ended" },
                )
                if (req.statement.isBlank()) {
                    _state.update {
                        it.copy(
                            error = "Proposal had no statement.",
                            savingProposals = it.savingProposals - messageId,
                        )
                    }
                    return@launch
                }
                a.createGoal(req)
                _state.update { st ->
                    st.copy(
                        info = "Saved goal: ${req.statement}",
                        messages = st.messages.map { m ->
                            if (m.id == messageId) m.copy(proposals = emptyList()) else m
                        },
                        savingProposals = st.savingProposals - messageId,
                    )
                }
                // Wake up the Goals/Today tabs so the new goal shows
                // immediately on tab switch instead of next app launch.
                com.buddy.app.data.RefreshBus.notifyGoals()
            } catch (e: retrofit2.HttpException) {
                if (e.code() == 409) {
                    _state.update {
                        it.copy(
                            error = "You're at 4 active goals. Pause one from Goals first.",
                            savingProposals = it.savingProposals - messageId,
                        )
                    }
                } else {
                    _state.update {
                        it.copy(
                            error = "Save failed: ${e.code()}",
                            savingProposals = it.savingProposals - messageId,
                        )
                    }
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        error = "Save failed: ${e.message}",
                        savingProposals = it.savingProposals - messageId,
                    )
                }
            }
        }
    }

    fun dismissProposal(messageId: String) {
        _state.update { st ->
            st.copy(messages = st.messages.map { m ->
                if (m.id == messageId) m.copy(proposals = emptyList()) else m
            })
        }
    }

    // --- Voice -------------------------------------------------------------

    fun onVoiceStarted() {
        _state.update { it.copy(isListening = true, partialTranscript = "") }
    }

    fun onVoicePartial(text: String) {
        _state.update { it.copy(partialTranscript = text) }
    }

    fun onVoiceFinal(text: String) {
        _state.update { it.copy(isListening = false, partialTranscript = "") }
        if (text.isNotBlank()) send(text)
    }

    fun onVoiceCancelled(error: String? = null) {
        _state.update {
            it.copy(
                isListening = false,
                partialTranscript = "",
                error = error,
            )
        }
    }

    private fun roleFor(api: String): ChatRole = when (api.lowercase()) {
        "assistant" -> ChatRole.ASSISTANT
        "user" -> ChatRole.USER
        else -> ChatRole.SYSTEM
    }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer {
                ChatViewModel(SettingsRepository(app))
            }
        }
    }
}

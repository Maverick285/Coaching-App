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
)

data class ChatUiState(
    val backendConfigured: Boolean = false,
    val messages: List<ChatMessage> = emptyList(),
    val composerText: String = "",
    val isSending: Boolean = false,
    val isListening: Boolean = false,
    val partialTranscript: String = "",
    val error: String? = null,
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

    fun startNewSession() {
        viewModelScope.launch {
            settings.clearSessionId()
            sessionId = null
            _state.update { it.copy(messages = emptyList(), composerText = "", error = null) }
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
                )
                _state.update {
                    it.copy(
                        messages = it.messages + assistant,
                        isSending = false,
                    )
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

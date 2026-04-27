package com.buddy.app.ui.customize

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.buddy.app.data.ApiHolder
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.HealthResponse
import com.buddy.app.data.MemoryFileWrite
import com.buddy.app.data.ProfileResponse
import com.buddy.app.data.ProfileUpdate
import com.buddy.app.data.SettingsRepository
import com.buddy.app.data.UsageResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Editable memory files that Customize exposes. */
val CUSTOMIZABLE_MEMORY_FILES = listOf("PERSONA.md", "MEMORY.md", "PATTERNS.md")

data class CustomizeUiState(
    val configured: Boolean = false,
    val loading: Boolean = false,
    val profile: ProfileResponse? = null,
    val userNameInput: String = "",
    val personaNameInput: String = "",
    val chatTierInput: String = "auto",  // auto | fast | reasoning
    val savingProfile: Boolean = false,
    val files: Map<String, String> = emptyMap(),     // path → content
    val editingPath: String? = null,
    val editorContent: String = "",
    val savingFile: Boolean = false,
    val health: HealthResponse? = null,
    val healthError: String? = null,
    val usage: UsageResponse? = null,
    val message: String? = null,
    val error: String? = null,
)

class CustomizeViewModel(
    application: Application,
    private val settingsRepo: SettingsRepository,
    holder: ApiHolder,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(CustomizeUiState())
    val state: StateFlow<CustomizeUiState> = _state.asStateFlow()

    private var api: BuddyApi? = null

    init {
        viewModelScope.launch {
            holder.apiFlow.collectLatest { value: BuddyApi? ->
                api = value
                _state.update { it.copy(configured = value != null) }
                if (value != null) refresh()
            }
        }
    }

    fun refresh() {
        val a = api ?: return
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null, healthError = null) }
            try {
                val profile = a.getProfile()
                val files = mutableMapOf<String, String>()
                for (path in CUSTOMIZABLE_MEMORY_FILES) {
                    try {
                        files[path] = a.memoryFile(path).content
                    } catch (_: Exception) {
                        // file might not exist yet (e.g. PATTERNS.md before any consolidation)
                    }
                }
                _state.update {
                    it.copy(
                        loading = false,
                        profile = profile,
                        userNameInput = profile.userName,
                        personaNameInput = profile.personaName,
                        chatTierInput = profile.chatTier,
                        files = files,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
            // Health + usage are best-effort and parallelized in spirit;
            // they don't block the rest of the screen.
            try {
                val health = a.health()
                _state.update { it.copy(health = health, healthError = null) }
            } catch (e: Exception) {
                _state.update { it.copy(health = null, healthError = e.message ?: "unreachable") }
            }
            try {
                val usage = a.usage()
                _state.update { it.copy(usage = usage) }
            } catch (_: Exception) {
                // Usage is non-fatal — old backends may not have the endpoint.
            }
        }
    }

    fun onClearMessage() = _state.update { it.copy(message = null) }
    fun onClearError() = _state.update { it.copy(error = null) }

    fun setUserName(value: String) =
        _state.update { it.copy(userNameInput = value) }

    fun setPersonaName(value: String) =
        _state.update { it.copy(personaNameInput = value) }

    fun setChatTier(value: String) {
        if (value !in setOf("auto", "fast", "reasoning")) return
        _state.update { it.copy(chatTierInput = value) }
    }

    fun saveProfile() {
        val a = api ?: return
        val s = _state.value
        viewModelScope.launch {
            _state.update { it.copy(savingProfile = true, error = null) }
            try {
                val updated = a.updateProfile(
                    ProfileUpdate(
                        userName = s.userNameInput.trim(),
                        personaName = s.personaNameInput.trim(),
                        chatTier = s.chatTierInput,
                    )
                )
                _state.update {
                    it.copy(
                        savingProfile = false,
                        profile = updated,
                        chatTierInput = updated.chatTier,
                        message = "Saved.",
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(savingProfile = false, error = e.message) }
            }
        }
    }

    fun openFile(path: String) {
        val current = _state.value.files[path].orEmpty()
        _state.update { it.copy(editingPath = path, editorContent = current) }
    }

    fun setEditorContent(value: String) =
        _state.update { it.copy(editorContent = value) }

    fun cancelEdit() =
        _state.update { it.copy(editingPath = null, editorContent = "") }

    fun saveFile() {
        val a = api ?: return
        val s = _state.value
        val path = s.editingPath ?: return
        viewModelScope.launch {
            _state.update { it.copy(savingFile = true, error = null) }
            try {
                a.memoryFileWrite(
                    path,
                    MemoryFileWrite(content = s.editorContent, commitMessage = "android: edit $path"),
                )
                _state.update {
                    it.copy(
                        savingFile = false,
                        files = it.files + (path to s.editorContent),
                        editingPath = null,
                        editorContent = "",
                        message = "$path saved.",
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(savingFile = false, error = e.message) }
            }
        }
    }

    fun resetOnboarding() {
        viewModelScope.launch {
            settingsRepo.setOnboardingComplete(false)
            _state.update { it.copy(message = "Onboarding will run on next launch.") }
        }
    }

    companion object {
        fun factory(app: Application): ViewModelProvider.Factory = viewModelFactory {
            initializer {
                CustomizeViewModel(app, SettingsRepository(app), ApiHolder(app))
            }
        }
    }
}

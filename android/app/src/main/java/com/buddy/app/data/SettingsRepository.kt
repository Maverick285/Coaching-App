package com.buddy.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "buddy_settings")

data class BuddySettings(
    val backendUrl: String = "",
    val authToken: String = "",
    val sessionId: String = "",
)

class SettingsRepository(private val context: Context) {

    private object Keys {
        val BACKEND_URL = stringPreferencesKey("backend_url")
        val AUTH_TOKEN = stringPreferencesKey("auth_token")
        val SESSION_ID = stringPreferencesKey("session_id")
    }

    val flow: Flow<BuddySettings> = context.dataStore.data.map { prefs ->
        BuddySettings(
            backendUrl = prefs[Keys.BACKEND_URL].orEmpty(),
            authToken = prefs[Keys.AUTH_TOKEN].orEmpty(),
            sessionId = prefs[Keys.SESSION_ID].orEmpty(),
        )
    }

    suspend fun setBackend(url: String, token: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.BACKEND_URL] = url.trim().trimEnd('/')
            prefs[Keys.AUTH_TOKEN] = token.trim()
        }
    }

    suspend fun setSessionId(sessionId: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.SESSION_ID] = sessionId
        }
    }

    suspend fun clearSessionId() {
        context.dataStore.edit { prefs ->
            prefs.remove(Keys.SESSION_ID)
        }
    }
}

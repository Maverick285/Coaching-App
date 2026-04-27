package com.buddy.app.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.buddy.app.BuildConfig
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "buddy_settings")

data class BuddySettings(
    val backendUrl: String = "",
    val authToken: String = "",
    val sessionId: String = "",
    val morningHour: Int = 7,
    val morningMinute: Int = 0,
    val endOfDayHour: Int = 21,
    val endOfDayMinute: Int = 0,
    val alarmsEnabled: Boolean = true,
    val onboardingComplete: Boolean = false,
)

class SettingsRepository(private val context: Context) {

    private object Keys {
        val BACKEND_URL = stringPreferencesKey("backend_url")
        val AUTH_TOKEN = stringPreferencesKey("auth_token")
        val SESSION_ID = stringPreferencesKey("session_id")
        val MORNING_HOUR = intPreferencesKey("morning_hour")
        val MORNING_MINUTE = intPreferencesKey("morning_minute")
        val EOD_HOUR = intPreferencesKey("eod_hour")
        val EOD_MINUTE = intPreferencesKey("eod_minute")
        val ALARMS_ENABLED = booleanPreferencesKey("alarms_enabled")
        val ONBOARDING_COMPLETE = booleanPreferencesKey("onboarding_complete")
    }

    val flow: Flow<BuddySettings> = context.dataStore.data.map { prefs ->
        // Backend URL + token fall back to build-time defaults baked in
        // via local.properties, so reinstalls don't lose connectivity.
        BuddySettings(
            backendUrl = prefs[Keys.BACKEND_URL]?.takeIf { it.isNotBlank() }
                ?: BuildConfig.DEFAULT_BACKEND_URL,
            authToken = prefs[Keys.AUTH_TOKEN]?.takeIf { it.isNotBlank() }
                ?: BuildConfig.DEFAULT_AUTH_TOKEN,
            sessionId = prefs[Keys.SESSION_ID].orEmpty(),
            morningHour = prefs[Keys.MORNING_HOUR] ?: 7,
            morningMinute = prefs[Keys.MORNING_MINUTE] ?: 0,
            endOfDayHour = prefs[Keys.EOD_HOUR] ?: 21,
            endOfDayMinute = prefs[Keys.EOD_MINUTE] ?: 0,
            alarmsEnabled = prefs[Keys.ALARMS_ENABLED] ?: true,
            onboardingComplete = prefs[Keys.ONBOARDING_COMPLETE] ?: false,
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

    suspend fun setMorning(hour: Int, minute: Int) {
        context.dataStore.edit { prefs ->
            prefs[Keys.MORNING_HOUR] = hour.coerceIn(0, 23)
            prefs[Keys.MORNING_MINUTE] = minute.coerceIn(0, 59)
        }
    }

    suspend fun setEndOfDay(hour: Int, minute: Int) {
        context.dataStore.edit { prefs ->
            prefs[Keys.EOD_HOUR] = hour.coerceIn(0, 23)
            prefs[Keys.EOD_MINUTE] = minute.coerceIn(0, 59)
        }
    }

    suspend fun setAlarmsEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.ALARMS_ENABLED] = enabled
        }
    }

    suspend fun setOnboardingComplete(complete: Boolean) {
        context.dataStore.edit { prefs ->
            prefs[Keys.ONBOARDING_COMPLETE] = complete
        }
    }
}

package com.buddy.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "buddy_settings")

import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.booleanPreferencesKey

data class BuddySettings(
    val backendUrl: String = "",
    val authToken: String = "",
    val sessionId: String = "",
    val morningHour: Int = 7,
    val morningMinute: Int = 0,
    val endOfDayHour: Int = 21,
    val endOfDayMinute: Int = 0,
    val alarmsEnabled: Boolean = true,
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
    }

    val flow: Flow<BuddySettings> = context.dataStore.data.map { prefs ->
        BuddySettings(
            backendUrl = prefs[Keys.BACKEND_URL].orEmpty(),
            authToken = prefs[Keys.AUTH_TOKEN].orEmpty(),
            sessionId = prefs[Keys.SESSION_ID].orEmpty(),
            morningHour = prefs[Keys.MORNING_HOUR] ?: 7,
            morningMinute = prefs[Keys.MORNING_MINUTE] ?: 0,
            endOfDayHour = prefs[Keys.EOD_HOUR] ?: 21,
            endOfDayMinute = prefs[Keys.EOD_MINUTE] ?: 0,
            alarmsEnabled = prefs[Keys.ALARMS_ENABLED] ?: true,
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
}

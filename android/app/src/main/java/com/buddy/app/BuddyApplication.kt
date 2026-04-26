package com.buddy.app

import android.app.Application
import com.buddy.app.data.SettingsRepository
import com.buddy.app.notifications.AlarmScheduler
import com.buddy.app.notifications.Notifications
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class BuddyApplication : Application() {

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onCreate() {
        super.onCreate()
        Notifications.ensureChannel(this)
        // Re-arm the daily alarms whenever the app process is created. Cheap;
        // AlarmManager dedupes via the same PendingIntent.
        appScope.launch {
            val settings = SettingsRepository(applicationContext).flow.first()
            if (settings.alarmsEnabled) {
                AlarmScheduler.scheduleAll(applicationContext, settings)
            }
        }
    }
}

package com.buddy.app.notifications

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.buddy.app.data.SettingsRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Fires from [AlarmScheduler]. Renders the appropriate notification, then
 * re-schedules itself for tomorrow (AlarmManager's setExactAndAllowWhileIdle
 * is one-shot).
 */
class DailyRhythmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val kind = intent.getStringExtra(EXTRA_KIND) ?: return
        when (kind) {
            KIND_MORNING -> Notifications.show(
                context,
                Notifications.NOTIF_ID_MORNING,
                title = "Morning check-in",
                body = "What's the par-1 plan for today? Tap to open Buddy.",
                deeplink = "goals",
            )
            KIND_EOD -> Notifications.show(
                context,
                Notifications.NOTIF_ID_EOD,
                title = "End of day",
                body = "Review today's grade and add a journal note if you want.",
                deeplink = "grade",
            )
        }
        // Reschedule for tomorrow.
        val pendingResult = goAsync()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        scope.launch {
            try {
                val settings = SettingsRepository(context)
                val current = settings.flow.first()
                if (current.alarmsEnabled) {
                    AlarmScheduler.scheduleAll(context, current)
                }
            } finally {
                pendingResult.finish()
            }
        }
    }

    companion object {
        const val ACTION = "com.buddy.app.DAILY_RHYTHM"
        const val EXTRA_KIND = "kind"
        const val KIND_MORNING = "morning"
        const val KIND_EOD = "eod"
    }
}

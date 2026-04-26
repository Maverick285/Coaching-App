package com.buddy.app.interventions

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationManagerCompat
import com.buddy.app.data.ApiClient
import com.buddy.app.data.InterventionAction
import com.buddy.app.data.SettingsRepository
import com.buddy.app.notifications.Notifications
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Fired when the user taps the "Got it" action on an intervention
 * notification. Cancels the notification locally + tells the backend
 * the intervention was dismissed (so the engine's grace period kicks
 * in and it doesn't immediately re-fire).
 */
class InterventionDismissReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getIntExtra(EXTRA_INTERVENTION_ID, 0)
        val notifId = intent.getIntExtra(EXTRA_NOTIF_ID, 0)
        if (id <= 0) return
        NotificationManagerCompat.from(context).cancel(notifId)

        val pendingResult = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                val settings = SettingsRepository(context).flow.first()
                val api = ApiClient.build(settings.backendUrl, settings.authToken)
                api?.interventionAction(id, InterventionAction(action = "dismissed"))
            } catch (_: Exception) {
                // Best-effort; the engine will eventually time-out the
                // tier escalation either way.
            } finally {
                pendingResult.finish()
            }
        }
    }

    companion object {
        const val ACTION = "com.buddy.app.INTERVENTION_DISMISS"
        const val EXTRA_INTERVENTION_ID = "intervention_id"
        const val EXTRA_NOTIF_ID = "notif_id"
    }
}

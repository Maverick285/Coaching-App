package com.buddy.app.interventions

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.buddy.app.MainActivity
import com.buddy.app.R
import com.buddy.app.data.Intervention
import com.buddy.app.notifications.Notifications

/**
 * Renders a backend Intervention as an Android notification, picking the
 * right channel + style for the tier.
 *
 * Tier 0 — IMPORTANCE_LOW, no sound, dismissable.
 * Tier 1 — IMPORTANCE_DEFAULT, gentle sound.
 * Tier 2 — IMPORTANCE_HIGH, ongoing (FLAG_NO_CLEAR), audible. Per spec:
 *          "audible, ongoing notification, requires explicit dismissal".
 */
object InterventionRenderer {

    fun render(context: Context, intervention: Intervention) {
        Notifications.ensureChannel(context)
        val notifId = Notifications.NOTIF_ID_INTERVENTION_BASE + intervention.id

        val openApp = PendingIntent.getActivity(
            context,
            notifId,
            Intent(context, MainActivity::class.java).apply {
                putExtra("deeplink", "focus")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val dismiss = PendingIntent.getBroadcast(
            context,
            notifId,
            Intent(context, InterventionDismissReceiver::class.java).apply {
                action = InterventionDismissReceiver.ACTION
                putExtra(InterventionDismissReceiver.EXTRA_INTERVENTION_ID, intervention.id)
                putExtra(InterventionDismissReceiver.EXTRA_NOTIF_ID, notifId)
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val (channel, title, ongoing) = when (intervention.tier) {
            0 -> Triple(Notifications.CHANNEL_INTERVENTION_T0, "Drift", false)
            1 -> Triple(Notifications.CHANNEL_INTERVENTION_T1, "Still drifting", false)
            else -> Triple(Notifications.CHANNEL_INTERVENTION_T2, "Take it back", true)
        }

        val builder = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(intervention.message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(intervention.message))
            .setContentIntent(openApp)
            .addAction(0, "Got it", dismiss)
            .setAutoCancel(!ongoing)
            .setOngoing(ongoing)
        if (intervention.tier == 2) {
            builder.setCategory(NotificationCompat.CATEGORY_REMINDER)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
        }

        try {
            NotificationManagerCompat.from(context).notify(notifId, builder.build())
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS denied — best-effort.
        }
    }

    fun cancel(context: Context, interventionId: Int) {
        val notifId = Notifications.NOTIF_ID_INTERVENTION_BASE + interventionId
        NotificationManagerCompat.from(context).cancel(notifId)
    }
}

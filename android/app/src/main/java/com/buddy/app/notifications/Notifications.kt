package com.buddy.app.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.buddy.app.MainActivity
import com.buddy.app.R

object Notifications {
    const val CHANNEL_DAILY = "daily_rhythm"
    const val CHANNEL_FOCUS = "focus_session"
    const val CHANNEL_FOCUS_CHECKIN = "focus_check_in"

    const val NOTIF_ID_MORNING = 100
    const val NOTIF_ID_EOD = 101
    const val NOTIF_ID_FOCUS = 200          // persistent during a session
    const val NOTIF_ID_FOCUS_CHECKIN = 201  // each check-in toast

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = ContextCompat.getSystemService(context, NotificationManager::class.java)
                ?: return
            if (mgr.getNotificationChannel(CHANNEL_DAILY) == null) {
                val channel = NotificationChannel(
                    CHANNEL_DAILY,
                    "Daily rhythm",
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = "Morning check-in and end-of-day grading prompts."
                }
                mgr.createNotificationChannel(channel)
            }
            if (mgr.getNotificationChannel(CHANNEL_FOCUS) == null) {
                val channel = NotificationChannel(
                    CHANNEL_FOCUS,
                    "Focus session",
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    description = "Persistent presence while a focus session is active."
                    setShowBadge(false)
                }
                mgr.createNotificationChannel(channel)
            }
            if (mgr.getNotificationChannel(CHANNEL_FOCUS_CHECKIN) == null) {
                val channel = NotificationChannel(
                    CHANNEL_FOCUS_CHECKIN,
                    "Focus check-ins",
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = "Mid-session check-in messages from your coach."
                }
                mgr.createNotificationChannel(channel)
            }
        }
    }

    fun show(
        context: Context,
        notifId: Int,
        title: String,
        body: String,
        deeplink: String? = null,
    ) {
        ensureChannel(context)
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            if (deeplink != null) putExtra("deeplink", deeplink)
        }
        val pi = PendingIntent.getActivity(
            context,
            notifId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notif = NotificationCompat.Builder(context, CHANNEL_DAILY)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(pi)
            .setAutoCancel(true)
            .build()
        val mgr = ContextCompat.getSystemService(context, NotificationManager::class.java)
        mgr?.notify(notifId, notif)
    }
}

package com.buddy.app.focus

import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.buddy.app.MainActivity
import com.buddy.app.R
import com.buddy.app.data.AgentHeartbeat
import com.buddy.app.data.ApiClient
import com.buddy.app.data.BuddyApi
import com.buddy.app.data.SettingsRepository
import com.buddy.app.interventions.InterventionRenderer
import com.buddy.app.interventions.PhoneCategorizer
import com.buddy.app.interventions.UsageStatsReader
import com.buddy.app.notifications.Notifications
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Foreground service that keeps a session alive in the user's awareness:
 *
 *   - Persistent low-importance notification with intention + remaining time,
 *     refreshed once per minute.
 *   - Scheduled "presence" check-ins at fixed offsets (default 15, 30, then
 *     "end" at -3 minutes). Each check-in calls the backend's
 *     /focus/{id}/check-in endpoint to get a persona-calibrated message and
 *     posts it on the higher-priority CHANNEL_FOCUS_CHECKIN channel.
 *   - Stops itself automatically when the planned duration elapses.
 *
 * Lifecycle: started by FocusViewModel.startSession; stopped by either
 * FocusViewModel.endSession (which also calls /focus/{id}/end on the backend)
 * or by ACTION_STOP intent from the notification's "End" action.
 */
class FocusSessionService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var sessionId: Int = 0
    private var intention: String = ""
    private var startedAtMs: Long = 0L
    private var plannedMinutes: Int = 45
    private var checkInJob: Job? = null
    private var refreshJob: Job? = null
    private var heartbeatJob: Job? = null
    private var pollJob: Job? = null
    private val seenInterventions = mutableSetOf<Int>()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> handleStart(intent)
            ACTION_STOP -> handleStop()
            else -> stopSelf()
        }
        return START_NOT_STICKY
    }

    private fun handleStart(intent: Intent) {
        sessionId = intent.getIntExtra(EXTRA_SESSION_ID, 0)
        intention = intent.getStringExtra(EXTRA_INTENTION).orEmpty()
        plannedMinutes = intent.getIntExtra(EXTRA_PLANNED_MIN, 45)
        startedAtMs = System.currentTimeMillis()

        Notifications.ensureChannel(this)
        startForeground(Notifications.NOTIF_ID_FOCUS, buildPresenceNotification())

        refreshJob?.cancel()
        refreshJob = scope.launch {
            while (true) {
                delay(60_000)
                val remaining = remainingMinutes()
                if (remaining <= 0) {
                    handleStop()
                    return@launch
                }
                updatePresenceNotification()
            }
        }

        checkInJob?.cancel()
        checkInJob = scope.launch {
            // Default schedule: presence at 15 + 30 min, end at planned - 3.
            val schedule = listOf(
                15 to "presence",
                30 to "presence",
                (plannedMinutes - 3).coerceAtLeast(5) to "end",
            ).filter { it.first in 1 until plannedMinutes }
                .distinctBy { it.first }
                .sortedBy { it.first }

            for ((minute, kind) in schedule) {
                val targetMs = startedAtMs + minute * 60_000L
                val sleep = targetMs - System.currentTimeMillis()
                if (sleep > 0) delay(sleep)
                if (remainingMinutes() <= 0) return@launch
                fireCheckIn(kind)
            }
        }

        // Phase 4: heartbeat the phone-side foreground category every 15s
        // and poll for pending interventions every 20s.
        heartbeatJob?.cancel()
        heartbeatJob = scope.launch {
            var lastReportMs = System.currentTimeMillis()
            while (true) {
                delay(15_000)
                if (remainingMinutes() <= 0) return@launch
                val now = System.currentTimeMillis()
                val activeSeconds = ((now - lastReportMs) / 1000L).toInt()
                lastReportMs = now
                sendHeartbeat(activeSeconds)
            }
        }

        pollJob?.cancel()
        pollJob = scope.launch {
            while (true) {
                delay(20_000)
                if (remainingMinutes() <= 0) return@launch
                pollPendingInterventions()
            }
        }
    }

    private fun handleStop() {
        refreshJob?.cancel()
        checkInJob?.cancel()
        heartbeatJob?.cancel()
        pollJob?.cancel()
        // minSdk = 28 ≥ N, so STOP_FOREGROUND_REMOVE is always available.
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        refreshJob?.cancel()
        checkInJob?.cancel()
        heartbeatJob?.cancel()
        pollJob?.cancel()
        scope.coroutineContext[Job]?.cancel()
        super.onDestroy()
    }

    private fun remainingMinutes(): Int {
        val elapsed = ((System.currentTimeMillis() - startedAtMs) / 60_000L).toInt()
        return (plannedMinutes - elapsed).coerceAtLeast(0)
    }

    private fun updatePresenceNotification() {
        val notif = buildPresenceNotification()
        try {
            androidx.core.app.NotificationManagerCompat.from(this)
                .notify(Notifications.NOTIF_ID_FOCUS, notif)
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS denied; persistent presence is best-effort.
        }
    }

    private fun buildPresenceNotification(): android.app.Notification {
        val openApp = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java).apply {
                putExtra("deeplink", "focus")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val stopIntent = PendingIntent.getService(
            this,
            1,
            Intent(this, FocusSessionService::class.java).apply { action = ACTION_STOP },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val remaining = remainingMinutes()
        return NotificationCompat.Builder(this, Notifications.CHANNEL_FOCUS)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(intention.ifEmpty { "Focus session" })
            .setContentText("$remaining min remaining")
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setContentIntent(openApp)
            .addAction(0, "End", stopIntent)
            .build()
    }

    private suspend fun fireCheckIn(kind: String) {
        val api = buildApi() ?: return
        try {
            val resp = api.fireCheckIn(sessionId, kind)
            postCheckInNotification(resp.checkIn.message)
        } catch (_: Exception) {
            postCheckInNotification(
                if (kind == "end") "5 minutes left." else "Still here."
            )
        }
    }

    private fun postCheckInNotification(message: String) {
        val openApp = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java).apply {
                putExtra("deeplink", "focus")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notif = NotificationCompat.Builder(this, Notifications.CHANNEL_FOCUS_CHECKIN)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle("Coach")
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setAutoCancel(true)
            .setContentIntent(openApp)
            .build()
        try {
            androidx.core.app.NotificationManagerCompat.from(this)
                .notify(Notifications.NOTIF_ID_FOCUS_CHECKIN, notif)
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS denied; check-in is logged on the backend regardless.
        }
    }

    private suspend fun buildApi(): BuddyApi? {
        val settings = SettingsRepository(applicationContext).flow.first()
        return ApiClient.build(settings.backendUrl, settings.authToken)
    }

    private suspend fun sendHeartbeat(activeSeconds: Int) {
        val api = buildApi() ?: return
        val pkg = UsageStatsReader.currentForegroundPackage(applicationContext)
        val category = PhoneCategorizer.categorize(pkg)
        try {
            api.agentHeartbeat(
                AgentHeartbeat(
                    source = "phone_usage_stats",
                    foregroundCategory = category,
                    foregroundAppHint = pkg.orEmpty(),
                    idleSeconds = 0,
                    activeSeconds = activeSeconds,
                )
            )
        } catch (_: Exception) {
            // Best-effort. Engine still has whatever PC agent reports landed.
        }
    }

    private suspend fun pollPendingInterventions() {
        val api = buildApi() ?: return
        val pending = try {
            api.pendingInterventions().interventions
        } catch (_: Exception) {
            return
        }
        for (intervention in pending) {
            if (!seenInterventions.add(intervention.id)) continue
            InterventionRenderer.render(applicationContext, intervention)
            try {
                api.interventionAction(
                    intervention.id,
                    com.buddy.app.data.InterventionAction(action = "delivered"),
                )
            } catch (_: Exception) {
                // Best-effort.
            }
        }
    }

    companion object {
        const val ACTION_START = "com.buddy.app.focus.START"
        const val ACTION_STOP = "com.buddy.app.focus.STOP"
        const val EXTRA_SESSION_ID = "session_id"
        const val EXTRA_INTENTION = "intention"
        const val EXTRA_PLANNED_MIN = "planned_min"

        fun start(
            context: Context,
            sessionId: Int,
            intention: String,
            plannedMinutes: Int,
        ) {
            val intent = Intent(context, FocusSessionService::class.java).apply {
                action = ACTION_START
                putExtra(EXTRA_SESSION_ID, sessionId)
                putExtra(EXTRA_INTENTION, intention)
                putExtra(EXTRA_PLANNED_MIN, plannedMinutes)
            }
            ContextCompat.startForegroundService(context, intent)
        }

        fun stop(context: Context) {
            val intent = Intent(context, FocusSessionService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }
    }
}

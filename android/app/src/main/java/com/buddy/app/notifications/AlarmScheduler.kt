package com.buddy.app.notifications

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.content.ContextCompat
import com.buddy.app.data.BuddySettings
import java.util.Calendar

object AlarmScheduler {

    private const val REQUEST_MORNING = 1001
    private const val REQUEST_EOD = 1002

    fun scheduleAll(context: Context, settings: BuddySettings) {
        if (!settings.alarmsEnabled) return
        scheduleOne(
            context,
            requestCode = REQUEST_MORNING,
            kind = DailyRhythmReceiver.KIND_MORNING,
            hour = settings.morningHour,
            minute = settings.morningMinute,
        )
        scheduleOne(
            context,
            requestCode = REQUEST_EOD,
            kind = DailyRhythmReceiver.KIND_EOD,
            hour = settings.endOfDayHour,
            minute = settings.endOfDayMinute,
        )
    }

    fun cancelAll(context: Context) {
        cancelOne(context, REQUEST_MORNING, DailyRhythmReceiver.KIND_MORNING)
        cancelOne(context, REQUEST_EOD, DailyRhythmReceiver.KIND_EOD)
    }

    private fun scheduleOne(
        context: Context,
        requestCode: Int,
        kind: String,
        hour: Int,
        minute: Int,
    ) {
        val mgr = ContextCompat.getSystemService(context, AlarmManager::class.java) ?: return
        val pi = pendingIntent(context, requestCode, kind)
        val triggerAt = nextOccurrence(hour, minute)
        val canExact = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            mgr.canScheduleExactAlarms()
        } else {
            true
        }
        try {
            if (canExact) {
                mgr.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi)
            } else {
                mgr.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi)
            }
        } catch (_: SecurityException) {
            // Exact-alarm permission revoked; fall back to inexact.
            mgr.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi)
        }
    }

    private fun cancelOne(context: Context, requestCode: Int, kind: String) {
        val mgr = ContextCompat.getSystemService(context, AlarmManager::class.java) ?: return
        mgr.cancel(pendingIntent(context, requestCode, kind))
    }

    private fun pendingIntent(context: Context, requestCode: Int, kind: String): PendingIntent {
        val intent = Intent(context, DailyRhythmReceiver::class.java).apply {
            action = DailyRhythmReceiver.ACTION
            putExtra(DailyRhythmReceiver.EXTRA_KIND, kind)
        }
        return PendingIntent.getBroadcast(
            context,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun nextOccurrence(hour: Int, minute: Int): Long {
        val now = Calendar.getInstance()
        val target = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        if (!target.after(now)) target.add(Calendar.DAY_OF_YEAR, 1)
        return target.timeInMillis
    }
}

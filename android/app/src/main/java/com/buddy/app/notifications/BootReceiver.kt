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

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED &&
            intent.action != Intent.ACTION_LOCKED_BOOT_COMPLETED
        ) return
        val pendingResult = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                val settings = SettingsRepository(context).flow.first()
                if (settings.alarmsEnabled) {
                    AlarmScheduler.scheduleAll(context, settings)
                }
            } finally {
                pendingResult.finish()
            }
        }
    }
}

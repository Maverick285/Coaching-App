package com.buddy.app.interventions

import android.app.AppOpsManager
import android.app.usage.UsageStatsManager
import android.content.Context
import android.os.Process
import androidx.core.content.ContextCompat

/**
 * Reads the foreground app via UsageStatsManager. This requires the
 * `PACKAGE_USAGE_STATS` permission, which on Android isn't grantable
 * via the normal runtime-permission flow — the user has to toggle it
 * manually from Settings → Special access → Usage access.
 *
 * Returns null if permission isn't granted (caller should treat as "no
 * signal" rather than failing the session).
 */
object UsageStatsReader {

    fun hasPermission(context: Context): Boolean {
        val appOps = ContextCompat.getSystemService(context, AppOpsManager::class.java)
            ?: return false
        // unsafeCheckOpNoThrow is API 29+; the deprecated checkOpNoThrow
        // works on minSdk 28 with the same semantics.
        @Suppress("DEPRECATION")
        val mode = appOps.checkOpNoThrow(
            AppOpsManager.OPSTR_GET_USAGE_STATS,
            Process.myUid(),
            context.packageName,
        )
        return mode == AppOpsManager.MODE_ALLOWED
    }

    fun currentForegroundPackage(context: Context, lookbackMillis: Long = 30_000): String? {
        if (!hasPermission(context)) return null
        val mgr = ContextCompat.getSystemService(context, UsageStatsManager::class.java)
            ?: return null
        val end = System.currentTimeMillis()
        val start = end - lookbackMillis
        val stats = mgr.queryUsageStats(UsageStatsManager.INTERVAL_BEST, start, end)
            ?: return null
        return stats
            .filter { it.lastTimeUsed in (start + 1)..end }
            .maxByOrNull { it.lastTimeUsed }
            ?.packageName
    }
}

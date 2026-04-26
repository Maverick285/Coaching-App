package com.buddy.app.blocking

import android.content.Context
import com.buddy.app.data.ApiClient
import com.buddy.app.data.SettingsRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.time.OffsetDateTime

/**
 * Pure object — no Service. Started/stopped by [com.buddy.app.focus.FocusSessionService]
 * during a session, polls /blocked-apps/active every 5 seconds and
 * pushes the snapshot into [BlockState].
 *
 * 5s is fast enough that opening a blocked app catches the new rule
 * within a single Compose foreground change, slow enough not to drain
 * battery. The accessibility service responds in real time once the
 * snapshot is in [BlockState].
 */
object BlockPollService {

    private const val POLL_SECONDS = 5
    private val scope = CoroutineScope(SupervisorJob() + kotlinx.coroutines.Dispatchers.IO)
    @Volatile private var job: Job? = null

    fun start(context: Context) {
        if (job != null) return
        val ctx = context.applicationContext
        job = scope.launch {
            while (true) {
                refreshOnce(ctx)
                delay(POLL_SECONDS * 1000L)
            }
        }
    }

    fun stop() {
        job?.cancel()
        job = null
        BlockState.clear()
    }

    private suspend fun refreshOnce(context: Context) {
        val settings = SettingsRepository(context).flow.first()
        val api = ApiClient.build(settings.backendUrl, settings.authToken) ?: return
        try {
            val resp = api.activeBlocks()
            val expiresMs = resp.overrideExpiresAt?.let {
                runCatching { OffsetDateTime.parse(it).toInstant().toEpochMilli() }.getOrNull()
            }
            BlockState.update(
                blocks = resp.blocks,
                overrideOpen = resp.overrideWindowOpen,
                overrideExpiresAtMs = expiresMs,
            )
        } catch (_: Exception) {
            // Best-effort. Stale state is fine — accessibility service won't
            // newly block anything that wasn't already in the last snapshot.
        }
    }
}

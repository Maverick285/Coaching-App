package com.buddy.app.blocking

import com.buddy.app.data.ActiveBlock
import java.util.concurrent.atomic.AtomicReference

/**
 * Process-wide cache of "what apps am I currently blocking?", filled by
 * [BlockPollService] and read by [BuddyAccessibilityService] on every
 * window-state-change event.
 *
 * AtomicReference because the accessibility service callback runs on the
 * system's binder thread; any read needs to be lock-free.
 */
object BlockState {

    private data class Snapshot(
        val rulesByPackage: Map<String, ActiveBlock>,
        val overrideOpen: Boolean,
        val overrideExpiresAtMs: Long?,
    )

    private val ref = AtomicReference(
        Snapshot(emptyMap(), overrideOpen = false, overrideExpiresAtMs = null)
    )

    fun update(blocks: List<ActiveBlock>, overrideOpen: Boolean, overrideExpiresAtMs: Long?) {
        ref.set(
            Snapshot(
                rulesByPackage = blocks.associateBy { it.packageName },
                overrideOpen = overrideOpen,
                overrideExpiresAtMs = overrideExpiresAtMs,
            )
        )
    }

    fun ruleFor(packageName: String?): ActiveBlock? {
        if (packageName == null) return null
        val s = ref.get()
        if (s.overrideOpen) return null
        return s.rulesByPackage[packageName]
    }

    fun isOverrideOpen(): Boolean = ref.get().overrideOpen

    fun overrideExpiresAtMs(): Long? = ref.get().overrideExpiresAtMs

    fun clear() {
        ref.set(Snapshot(emptyMap(), overrideOpen = false, overrideExpiresAtMs = null))
    }
}

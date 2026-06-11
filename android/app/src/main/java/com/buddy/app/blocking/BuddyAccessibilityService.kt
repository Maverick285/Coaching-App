package com.buddy.app.blocking

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.app.ActivityManager
import android.content.Intent
import android.os.Build
import android.view.accessibility.AccessibilityEvent
import androidx.core.content.ContextCompat

/**
 * Listens for window-state-change events and, when the new foreground
 * package matches an active block in [BlockState], either:
 *
 *   - Tier 3 (friction): launches [FrictionOverlayActivity] over the app.
 *     The user can wait 60 s + type a reason, then proceed.
 *   - Tier 4 (hard block): performs GLOBAL_ACTION_HOME to send the user
 *     back to the launcher, then launches a brief explanatory activity.
 *
 * Per spec §6 'It does not shame. It does not catastrophize.'
 *
 * Permission: requires the user to grant accessibility access from
 * Settings → Accessibility → Buddy → toggle on. The grant flow is
 * surfaced from the Customize screen with a clear explanation of
 * exactly what the service does (foreground app monitoring; nothing
 * else).
 */
class BuddyAccessibilityService : AccessibilityService() {

    private var lastHandledPackage: String? = null
    private var lastHandledAtMs: Long = 0L

    override fun onServiceConnected() {
        super.onServiceConnected()
        val info = AccessibilityServiceInfo().apply {
            eventTypes = AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED or
                AccessibilityEvent.TYPE_WINDOWS_CHANGED
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
            // We only need package names — no node-tree walk, no text.
            flags = AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
            notificationTimeout = 50
        }
        serviceInfo = info
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val pkg = event?.packageName?.toString() ?: return
        if (pkg == packageName) return // never block ourselves
        if (pkg == "com.android.systemui") return
        // Debounce: same package within 1.5 s shouldn't re-fire.
        val now = System.currentTimeMillis()
        if (pkg == lastHandledPackage && now - lastHandledAtMs < 1500) return

        val rule = BlockState.ruleFor(pkg) ?: return
        lastHandledPackage = pkg
        lastHandledAtMs = now

        when (rule.blockTier) {
            3 -> launchFriction(pkg, rule.goalId, rule.sessionId)
            4 -> hardBlock(pkg, rule.goalId, rule.sessionId)
            else -> Unit
        }
    }

    override fun onInterrupt() {}

    private fun launchFriction(pkg: String, goalId: Int, sessionId: Int) {
        val intent = Intent(this, FrictionOverlayActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            putExtra(FrictionOverlayActivity.EXTRA_PACKAGE, pkg)
            putExtra(FrictionOverlayActivity.EXTRA_GOAL_ID, goalId)
            putExtra(FrictionOverlayActivity.EXTRA_SESSION_ID, sessionId)
            putExtra(FrictionOverlayActivity.EXTRA_BLOCK_TIER, 3)
        }
        ContextCompat.startActivity(this, intent, null)
    }

    private fun hardBlock(pkg: String, goalId: Int, sessionId: Int) {
        // First send the user back to home so they're not staring at the
        // forbidden app while we render the override prompt.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN) {
            performGlobalAction(GLOBAL_ACTION_HOME)
        } else {
            val home = Intent(Intent.ACTION_MAIN).apply {
                addCategory(Intent.CATEGORY_HOME)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(home)
        }
        // Best-effort: also nudge the foreground task off the back stack.
        val am = ContextCompat.getSystemService(this, ActivityManager::class.java)
        try {
            am?.appTasks?.forEach { task ->
                if (task.taskInfo.baseActivity?.packageName == pkg) task.finishAndRemoveTask()
            }
        } catch (_: Exception) {
            // Some OEMs revoke this; the home action is the durable mitigation.
        }
        // Then surface the override prompt as a normal activity.
        val intent = Intent(this, FrictionOverlayActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            putExtra(FrictionOverlayActivity.EXTRA_PACKAGE, pkg)
            putExtra(FrictionOverlayActivity.EXTRA_GOAL_ID, goalId)
            putExtra(FrictionOverlayActivity.EXTRA_SESSION_ID, sessionId)
            putExtra(FrictionOverlayActivity.EXTRA_BLOCK_TIER, 4)
        }
        startActivity(intent)
    }
}

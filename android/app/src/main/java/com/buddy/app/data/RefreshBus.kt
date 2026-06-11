package com.buddy.app.data

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * Tiny app-wide event bus for "something changed, refresh your view."
 *
 * Used because Compose ViewModels are scoped per-NavBackStackEntry: a
 * Goals VM created on first visit doesn't observe a chat-driven save
 * unless something tells it. A SharedFlow with replay=0 is the
 * lightest-weight cross-VM signal we can emit.
 *
 * Emit via `RefreshBus.notifyGoals()` from anywhere; collect from any
 * VM that lists goals/tasks/grades. No platform deps, no activity
 * lifecycle gymnastics — just a shared coroutine flow.
 */
object RefreshBus {
    private val _goals = MutableSharedFlow<Unit>(extraBufferCapacity = 4)
    val goals: SharedFlow<Unit> = _goals.asSharedFlow()

    suspend fun notifyGoals() {
        _goals.emit(Unit)
    }
}

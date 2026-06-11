package com.buddy.app.data

import android.content.Context
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map

/**
 * One BuddyApi instance keyed by (backendUrl, authToken). When either changes,
 * a fresh API is built; otherwise the cached one is returned. Lets every
 * Phase 2 ViewModel observe the same Flow without each one rebuilding the
 * Retrofit graph on every emission.
 */
class ApiHolder(context: Context) {
    private val settings = SettingsRepository(context)

    val apiFlow: Flow<BuddyApi?> = settings.flow
        .map { it.backendUrl to it.authToken }
        .distinctUntilChanged()
        .map { (url, token) -> ApiClient.build(url, token) }
}

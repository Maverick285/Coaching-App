package com.buddy.app

import android.app.Application

/**
 * Hosts the Application context that DataStore (in [com.buddy.app.data.SettingsRepository])
 * and ViewModel factories use. No manual DI for Phase 1; the app is small enough that
 * direct construction works fine.
 */
class BuddyApplication : Application()

package com.buddy.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import com.buddy.app.data.SettingsRepository
import com.buddy.app.ui.AppNavGraph
import com.buddy.app.ui.Routes
import com.buddy.app.ui.theme.BuddyTheme
import kotlinx.coroutines.flow.first

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val deeplink = intent?.getStringExtra("deeplink")
        setContent { BuddyApp(deeplink = deeplink) }
    }
}

@Composable
private fun BuddyApp(deeplink: String?) {
    BuddyTheme {
        val context = LocalContext.current
        var startRoute by remember { mutableStateOf<String?>(null) }

        LaunchedEffect(Unit) {
            val settings = SettingsRepository(context).flow.first()
            // First-launch onboarding gate. A user who finished onboarding can
            // re-enter via Settings → Re-run onboarding.
            startRoute = when {
                !settings.onboardingComplete -> Routes.ONBOARDING
                deeplink == "goals" -> Routes.GOALS
                deeplink == "focus" -> Routes.FOCUS
                deeplink == "grade" -> Routes.GRADE
                deeplink == "journal" -> Routes.JOURNAL
                deeplink == "chat" -> Routes.CHAT
                deeplink == "tasks" -> Routes.TASKS
                else -> Routes.TASKS
            }
        }

        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background,
        ) {
            // Wait until DataStore is read to know the start route.
            startRoute?.let { route -> AppNavGraph(startRoute = route) }
        }
    }
}

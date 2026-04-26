package com.buddy.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.buddy.app.ui.AppNavGraph
import com.buddy.app.ui.Routes
import com.buddy.app.ui.theme.BuddyTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val deeplink = intent?.getStringExtra("deeplink")
        val start = when (deeplink) {
            "goals" -> Routes.GOALS
            "focus" -> Routes.FOCUS
            "grade" -> Routes.GRADE
            "journal" -> Routes.JOURNAL
            "chat" -> Routes.CHAT
            else -> Routes.CHAT
        }
        setContent { BuddyApp(startRoute = start) }
    }
}

@Composable
private fun BuddyApp(startRoute: String) {
    BuddyTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            AppNavGraph(startRoute = startRoute)
        }
    }
}

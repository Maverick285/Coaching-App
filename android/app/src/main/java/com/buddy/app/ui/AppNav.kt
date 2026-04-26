package com.buddy.app.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.AssignmentTurnedIn
import androidx.compose.material.icons.filled.CenterFocusStrong
import androidx.compose.material.icons.filled.Flag
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.buddy.app.focus.FocusScreen
import com.buddy.app.ui.chat.ChatScreen
import com.buddy.app.ui.customize.CustomizeScreen
import com.buddy.app.ui.goals.GoalDetailScreen
import com.buddy.app.ui.goals.GoalsScreen
import com.buddy.app.ui.grade.GradeScreen
import com.buddy.app.ui.journal.JournalScreen
import com.buddy.app.ui.onboarding.OnboardingScreen
import com.buddy.app.ui.settings.SettingsScreen

object Routes {
    const val ONBOARDING = "onboarding"
    const val CHAT = "chat"
    const val GOALS = "goals"
    const val FOCUS = "focus"
    const val GRADE = "grade"
    const val JOURNAL = "journal"
    const val SETTINGS = "settings"
    const val CUSTOMIZE = "customize"
    const val GOAL_DETAIL = "goal/{goalId}"
    fun goalDetail(goalId: Int) = "goal/$goalId"
}

private data class TopLevelDestination(
    val route: String,
    val label: String,
    val icon: ImageVector,
)

private val TopLevelDestinations = listOf(
    TopLevelDestination(Routes.CHAT, "Chat", Icons.AutoMirrored.Filled.Chat),
    TopLevelDestination(Routes.GOALS, "Goals", Icons.Filled.Flag),
    TopLevelDestination(Routes.FOCUS, "Focus", Icons.Filled.CenterFocusStrong),
    TopLevelDestination(Routes.GRADE, "Grade", Icons.Filled.AssignmentTurnedIn),
    TopLevelDestination(Routes.JOURNAL, "Journal", Icons.AutoMirrored.Filled.MenuBook),
)

@Composable
fun AppNavGraph(
    navController: NavHostController = rememberNavController(),
    startRoute: String = Routes.CHAT,
) {
    val backStack by navController.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route

    val showBottomBar = currentRoute in TopLevelDestinations.map { it.route }

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.surface,
                ) {
                    TopLevelDestinations.forEach { dest ->
                        NavigationBarItem(
                            selected = currentRoute == dest.route,
                            onClick = {
                                if (currentRoute != dest.route) {
                                    navController.navigate(dest.route) {
                                        popUpTo(navController.graph.startDestinationId) {
                                            saveState = true
                                        }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                }
                            },
                            icon = { Icon(dest.icon, contentDescription = dest.label) },
                            label = { Text(dest.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = startRoute,
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            composable(Routes.CHAT) {
                ChatScreen(
                    onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                )
            }
            composable(Routes.GOALS) {
                GoalsScreen(
                    onGoalClicked = { goalId ->
                        navController.navigate(Routes.goalDetail(goalId))
                    },
                )
            }
            composable(
                Routes.GOAL_DETAIL,
                arguments = listOf(navArgument("goalId") { type = NavType.IntType }),
            ) { entry ->
                val goalId = entry.arguments?.getInt("goalId") ?: return@composable
                GoalDetailScreen(
                    goalId = goalId,
                    onBack = { navController.popBackStack() },
                )
            }
            composable(Routes.FOCUS) { FocusScreen() }
            composable(Routes.GRADE) { GradeScreen() }
            composable(Routes.JOURNAL) { JournalScreen() }
            composable(Routes.SETTINGS) {
                SettingsScreen(
                    onBack = { navController.popBackStack() },
                    onOpenCustomize = { navController.navigate(Routes.CUSTOMIZE) },
                )
            }
            composable(Routes.CUSTOMIZE) {
                CustomizeScreen(onBack = { navController.popBackStack() })
            }
            composable(Routes.ONBOARDING) {
                OnboardingScreen(onComplete = {
                    navController.navigate(Routes.CHAT) {
                        popUpTo(Routes.ONBOARDING) { inclusive = true }
                    }
                })
            }
        }
    }
}

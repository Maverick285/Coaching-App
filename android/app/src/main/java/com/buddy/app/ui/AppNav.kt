package com.buddy.app.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Flag
import androidx.compose.material.icons.filled.Today
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
import com.buddy.app.ui.dreams.DreamsScreen
import com.buddy.app.ui.goals.BacklogScreen
import com.buddy.app.ui.goals.GoalDetailScreen
import com.buddy.app.ui.goals.GoalsScreen
import com.buddy.app.ui.grade.GradeScreen
import com.buddy.app.ui.journal.JournalScreen
import com.buddy.app.ui.onboarding.OnboardingScreen
import com.buddy.app.ui.settings.SettingsScreen
import com.buddy.app.ui.tasks.TasksScreen
import com.buddy.app.ui.today.TodayScreen

object Routes {
    const val ONBOARDING = "onboarding"
    const val TODAY = "today"
    const val CHAT = "chat"
    const val TASKS = "tasks"
    const val GOALS = "goals"
    const val FOCUS = "focus"
    const val GRADE = "grade"
    const val JOURNAL = "journal"
    const val DREAMS = "dreams"
    const val BACKLOG = "backlog"
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

// Bottom nav per master spec §23.1: Home/Today, Goals, Coach, Dreams.
// Tasks/Focus/Journal/Grade live as dedicated routes reachable via the
// Today screen, goal detail, or settings — they aren't daily-flow tabs.
private val TopLevelDestinations = listOf(
    TopLevelDestination(Routes.TODAY, "Today", Icons.Filled.Today),
    TopLevelDestination(Routes.GOALS, "Goals", Icons.Filled.Flag),
    TopLevelDestination(Routes.CHAT, "Coach", Icons.AutoMirrored.Filled.Chat),
    TopLevelDestination(Routes.DREAMS, "Dreams", Icons.Filled.AutoAwesome),
)

@Composable
fun AppNavGraph(
    navController: NavHostController = rememberNavController(),
    startRoute: String = Routes.TODAY,
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
                                    // Pop everything down to start
                                    // (Today) and re-navigate. We
                                    // intentionally drop the
                                    // saveState/restoreState pair —
                                    // it caused tab switches to land
                                    // on stale or wrong destinations
                                    // (tapping Today sometimes showed
                                    // Goals). Fresh mount per tab is
                                    // simpler and bulletproof.
                                    navController.navigate(dest.route) {
                                        popUpTo(
                                            navController.graph.startDestinationId
                                        ) { inclusive = false }
                                        launchSingleTop = true
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
            composable(Routes.TODAY) {
                TodayScreen(
                    onOpenGoals = {
                        navController.navigate(Routes.GOALS) { launchSingleTop = true }
                    },
                    onOpenChat = {
                        navController.navigate(Routes.CHAT) { launchSingleTop = true }
                    },
                    onOpenFocus = {
                        navController.navigate(Routes.FOCUS) { launchSingleTop = true }
                    },
                    onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                    onOpenCustomize = { navController.navigate(Routes.CUSTOMIZE) },
                    onOpenGoalDetail = { id ->
                        navController.navigate(Routes.goalDetail(id))
                    },
                )
            }
            composable(Routes.DREAMS) { DreamsScreen() }
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
                    onTalkItThrough = {
                        navController.navigate(Routes.CHAT) {
                            launchSingleTop = true
                        }
                    },
                    onOpenBacklog = {
                        navController.navigate(Routes.BACKLOG)
                    },
                )
            }
            composable(Routes.BACKLOG) {
                BacklogScreen(
                    onBack = { navController.popBackStack() },
                    onGoalClicked = { id -> navController.navigate(Routes.goalDetail(id)) },
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
            composable(Routes.TASKS) { TasksScreen() }
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
                    navController.navigate(Routes.TODAY) {
                        popUpTo(Routes.ONBOARDING) { inclusive = true }
                    }
                })
            }
        }
    }
}

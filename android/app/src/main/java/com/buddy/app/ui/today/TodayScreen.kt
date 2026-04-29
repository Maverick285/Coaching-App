package com.buddy.app.ui.today

import android.app.Application
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.buddy.app.capture.CaptureActivity
import com.buddy.app.data.DayGrade
import com.buddy.app.data.FocusSession
import com.buddy.app.data.StreakResponse
import com.buddy.app.data.Task

/**
 * Home / Today screen. Per master spec §23.2 the job is to answer one
 * question: *what should I do right now?*
 *
 * Layout (§27.1):
 *   Top    — today's status (day grade, streak, persona greeting)
 *   Middle — the next-action card (active session / EOD / next task)
 *   Bottom — today's open tasks list (3-5 by spec; we show all open ones
 *            but sorted with the most relevant on top)
 *   FAB    — voice/text capture entry
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TodayScreen(
    onOpenGoals: () -> Unit,
    onOpenChat: () -> Unit,
    onOpenFocus: () -> Unit,
    onOpenSettings: () -> Unit = {},
    onOpenCustomize: () -> Unit = {},
    onOpenGoalDetail: (Int) -> Unit = {},
    viewModel: TodayViewModel = viewModel(
        factory = TodayViewModel.factory(
            LocalContext.current.applicationContext as Application
        )
    ),
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    val context = LocalContext.current
    var menuOpen by remember { mutableStateOf(false) }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbar.showSnackbar(it)
            viewModel.onClearError()
        }
    }

    // Refresh on first compose AND every time chat saves a goal or
    // logs progress.
    LaunchedEffect(Unit) {
        viewModel.refresh()
        com.buddy.app.data.RefreshBus.goals.collect {
            viewModel.refresh()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Today") },
                actions = {
                    // Three-dots overflow. Spec §23 puts settings
                    // behind nav, but the user shouldn't have to thread
                    // Chat → Settings to reach Customize. Today is
                    // every-launch, so the menu lives here.
                    IconButton(onClick = { menuOpen = true }) {
                        Icon(Icons.Filled.MoreVert, contentDescription = "Menu")
                    }
                    DropdownMenu(
                        expanded = menuOpen,
                        onDismissRequest = { menuOpen = false },
                    ) {
                        DropdownMenuItem(
                            text = { Text("Customize") },
                            onClick = {
                                menuOpen = false
                                onOpenCustomize()
                            },
                        )
                        DropdownMenuItem(
                            text = { Text("Settings") },
                            onClick = {
                                menuOpen = false
                                onOpenSettings()
                            },
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    titleContentColor = MaterialTheme.colorScheme.onBackground,
                ),
            )
        },
        floatingActionButton = {
            FloatingActionButton(
                onClick = {
                    context.startActivity(
                        android.content.Intent(context, CaptureActivity::class.java)
                            .putExtra(CaptureActivity.EXTRA_SOURCE, "today_fab")
                    )
                },
            ) { Icon(Icons.Filled.GraphicEq, contentDescription = "Quick capture") }
        },
        snackbarHost = { SnackbarHost(snackbar) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        when (state.mode) {
            TodayMode.NOT_CONFIGURED -> Column(
                modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
            ) {
                Text(
                    "Configure backend in Settings first.",
                    color = MaterialTheme.colorScheme.onBackground,
                )
            }
            TodayMode.LOADING -> Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { CircularProgressIndicator() }
            else -> LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item { StatusHeader(grade = state.grade, streak = state.streak) }
                item {
                    NextActionCard(
                        mode = state.mode,
                        activeSession = state.activeSession,
                        nextTask = state.openTasks.firstOrNull(),
                        nextTaskGoal = state.openTasks.firstOrNull()
                            ?.goalId
                            ?.let { state.goalsById[it] },
                        pendingDreams = state.pendingDreams,
                        onOpenGoals = onOpenGoals,
                        onOpenChat = onOpenChat,
                        onOpenFocus = onOpenFocus,
                    )
                }

                if (state.openTasks.isNotEmpty()) {
                    item {
                        Text(
                            "Today's tasks",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onBackground,
                            modifier = Modifier.padding(top = 8.dp, bottom = 4.dp),
                        )
                    }
                    items(state.openTasks.take(5), key = { it.id }) { t ->
                        val goal = state.goalsById[t.goalId]
                        TodayTaskRow(
                            task = t,
                            goalLabel = goal?.statement,
                            onToggle = { viewModel.toggleTaskDone(t) },
                            onClick = { goal?.let { onOpenGoalDetail(it.id) } },
                        )
                    }
                    if (state.openTasks.size > 5) {
                        item {
                            TextButton(onClick = onOpenGoals) {
                                Text("See all ${state.openTasks.size} open tasks →")
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StatusHeader(grade: DayGrade?, streak: StreakResponse?) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(
                verticalAlignment = Alignment.Bottom,
                modifier = Modifier.fillMaxWidth(),
            ) {
                // Grade is the largest element on the screen — par-1
                // is what the user is checking when they open the app.
                Text(
                    grade?.systemScore?.let { "%.1f".format(it) } ?: "—",
                    style = MaterialTheme.typography.displayLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(Modifier.size(10.dp))
                Text(
                    text = paceLabel(grade?.systemScore),
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(bottom = 8.dp),
                )
            }
            StreakRibbon(streak)
        }
    }
}

@Composable
private fun NextActionCard(
    mode: TodayMode,
    activeSession: FocusSession?,
    nextTask: Task?,
    nextTaskGoal: com.buddy.app.data.Goal?,
    pendingDreams: Int,
    onOpenGoals: () -> Unit,
    onOpenChat: () -> Unit,
    onOpenFocus: () -> Unit,
) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            when (mode) {
                TodayMode.ACTIVE_SESSION -> {
                    Text(
                        "Focus session running",
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    activeSession?.let {
                        Text(
                            "${it.plannedDurationMinutes} min planned · started ${prettyTime(it.startedAt)}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    androidx.compose.material3.Button(
                        onClick = onOpenFocus,
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Open session") }
                }
                TodayMode.EOD_PENDING -> {
                    Text(
                        "End of day check-in",
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Text(
                        "Today's grade is computed but not locked in. Want to review?",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    androidx.compose.material3.Button(
                        onClick = onOpenChat,
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Talk it through with the Coach") }
                }
                TodayMode.HAS_TASKS -> {
                    if (nextTask != null) {
                        Text(
                            "Next move",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                        Text(
                            nextTask.description,
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                        if (nextTask.first60Seconds.isNotBlank()) {
                            Text(
                                "Start with: ${nextTask.first60Seconds}",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        nextTaskGoal?.let {
                            Text(
                                "for: ${it.statement}",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        androidx.compose.material3.Button(
                            onClick = onOpenFocus,
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text("Start focus session") }
                    } else {
                        // HAS_TASKS but the first task isn't structured
                        // enough to surface as a "next move" — render a
                        // gentle prompt instead of an empty card.
                        Text(
                            "What's next?",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                        Text(
                            "Pick a task below or start a focus session against an active goal.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            androidx.compose.material3.OutlinedButton(
                                onClick = onOpenGoals,
                                modifier = Modifier.weight(1f),
                            ) { Text("Goals") }
                            androidx.compose.material3.Button(
                                onClick = onOpenFocus,
                                modifier = Modifier.weight(1f),
                            ) { Text("Start focus") }
                        }
                    }
                }
                TodayMode.EMPTY -> {
                    Text(
                        "Nothing scheduled",
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Text(
                        "Capture a thought, set a goal, or talk to the Coach.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        androidx.compose.material3.OutlinedButton(
                            onClick = onOpenGoals,
                            modifier = Modifier.weight(1f),
                        ) { Text("Goals") }
                        androidx.compose.material3.Button(
                            onClick = onOpenChat,
                            modifier = Modifier.weight(1f),
                        ) { Text("Coach") }
                    }
                }
                else -> Unit
            }
            if (pendingDreams > 0) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "$pendingDreams memory proposal${if (pendingDreams == 1) "" else "s"} waiting in Dreams.",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

@Composable
private fun StreakRibbon(streak: StreakResponse?) {
    if (streak == null) {
        Text(
            "Streak: —",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        return
    }
    val pauseCount = streak.pauseDays.size
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = "${streak.currentStreakLength}",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.size(6.dp))
            Text(
                text = if (streak.currentStreakLength == 1) "day unbroken" else "days unbroken",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (pauseCount > 0) {
                Text(
                    text = "  ·  $pauseCount paused",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        // Continuous ribbon, not isolated dots. A thin connecting track
        // with rounded segments per day reads as a chain — and the
        // ADHD-safe palette (§21.2) means brightness alone signals
        // state. Zero days are the only true alarm; everything else
        // sits on a primary-saturation gradient.
        StreakRibbonStrip(history = streak.history.takeLast(28))
    }
}

@Composable
private fun StreakRibbonStrip(history: List<com.buddy.app.data.StreakDay>) {
    val track = MaterialTheme.colorScheme.surfaceVariant
    val zero = MaterialTheme.colorScheme.error
    val pause = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.45f)
    val onPace = MaterialTheme.colorScheme.primary
    val belowPace = MaterialTheme.colorScheme.primary.copy(alpha = 0.55f)
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(10.dp)
            .background(track, androidx.compose.foundation.shape.RoundedCornerShape(5.dp)),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(1.dp),
        ) {
            history.forEach { d ->
                val color = when {
                    d.isZero -> zero
                    d.isPause -> pause
                    d.score >= 1.0 -> onPace
                    d.score > 0.0 -> belowPace
                    else -> track
                }
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .background(color),
                )
            }
        }
    }
}

@Composable
private fun TodayTaskRow(
    task: Task,
    goalLabel: String?,
    onToggle: () -> Unit,
    onClick: () -> Unit,
) {
    Card(
        onClick = onClick,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = task.state == "done", onCheckedChange = { onToggle() })
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    task.description,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    textDecoration = if (task.state == "done") TextDecoration.LineThrough else null,
                )
                if (!goalLabel.isNullOrBlank()) {
                    Text(
                        goalLabel,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            task.estimatedDurationMinutes?.let {
                Text(
                    "${it}m",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

private fun paceLabel(score: Double?): String = when {
    score == null -> "no data yet"
    score >= 1.5 -> "well above pace"
    score >= 1.0 -> "on pace"
    score > 0.0 -> "below pace"
    else -> "no progress yet"
}

private fun prettyTime(iso: String): String = try {
    val instant = if (iso.endsWith("Z") || iso.contains("+")) {
        java.time.OffsetDateTime.parse(iso).toInstant()
    } else {
        java.time.LocalDateTime.parse(iso).toInstant(java.time.ZoneOffset.UTC)
    }
    java.time.ZonedDateTime.ofInstant(instant, java.time.ZoneId.systemDefault())
        .format(java.time.format.DateTimeFormatter.ofPattern("HH:mm"))
} catch (_: Exception) {
    iso
}

package com.buddy.app.ui.goals

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberModalBottomSheetState
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.buddy.app.data.Goal
import com.buddy.app.data.GoalCreate
import com.buddy.app.data.WoopRequest
import com.buddy.app.data.WoopResponse
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GoalsScreen(
    onGoalClicked: (Int) -> Unit,
    onTalkItThrough: () -> Unit = {},
    onOpenBacklog: () -> Unit = {},
    viewModel: GoalsViewModel = viewModel(
        factory = GoalsViewModel.factory(LocalContext.current.applicationContext as Application)
    ),
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    var showChooser by remember { mutableStateOf(false) }
    var path by remember { mutableStateOf<NewGoalPath?>(null) }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbar.showSnackbar(it)
            viewModel.onClearError()
        }
    }

    // Refresh on every appearance — covers the case where a goal was
    // just saved from chat (or anywhere else) and the user lands on
    // this tab to see it. Without this, the VM only loads on first
    // entry and shows stale data.
    // Refresh on every appearance — covers chat-driven goal saves
    // and any other path that mutates the goal list off-screen.
    LaunchedEffect(Unit) {
        viewModel.refresh()
        com.buddy.app.data.RefreshBus.goals.collect {
            viewModel.refresh()
        }
    }

    // One-shot navigation: the create + plan-apply + pause-and-retry
    // paths all funnel into justCreatedGoalId. We close any open sheet,
    // pop to goal detail, then clear the event.
    LaunchedEffect(state.justCreatedGoalId, state.justStashed) {
        state.justCreatedGoalId?.let { id ->
            path = null
            onGoalClicked(id)
            viewModel.consumeJustCreated()
        }
        if (state.justStashed) {
            path = null
            snackbar.showSnackbar("Stashed in backlog.")
            viewModel.consumeJustCreated()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Goals")
                        // Slot count only when there's something to count.
                        // Avoids the prescriptive "0/4" empty state.
                        if (state.activeCount > 0) {
                            Text(
                                if (state.activeCount == 1) "1 active"
                                else "${state.activeCount} active",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                },
                actions = {
                    if (state.backlogCount > 0) {
                        TextButton(onClick = onOpenBacklog) {
                            Text("Backlog · ${state.backlogCount}")
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    titleContentColor = MaterialTheme.colorScheme.onBackground,
                ),
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { showChooser = true }) {
                Icon(Icons.Filled.Add, contentDescription = "Add goal")
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (!state.configured) {
                Text(
                    "Configure backend in Settings first.",
                    modifier = Modifier.padding(24.dp),
                    color = MaterialTheme.colorScheme.onBackground,
                )
            } else if (state.loading && state.goals.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else if (state.goals.isEmpty()) {
                Text(
                    "No goals yet. Tap + to set one.",
                    modifier = Modifier.padding(24.dp),
                    color = MaterialTheme.colorScheme.onBackground,
                )
            } else {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    contentPadding = PaddingValues(vertical = 12.dp),
                ) {
                    items(state.goals, key = { it.id }) { goal ->
                        GoalCard(goal, onClick = { onGoalClicked(goal.id) })
                    }
                }
            }
        }
    }

    if (showChooser) {
        NewGoalPathChooserSheet(
            onDismiss = { showChooser = false },
            onChoose = { chosen ->
                showChooser = false
                if (chosen == NewGoalPath.TALK) {
                    onTalkItThrough()
                } else {
                    path = chosen
                }
            },
        )
    }

    state.limitHit?.let { hit ->
        ActiveGoalLimitDialog(
            message = hit.message,
            activeGoals = state.goals,
            onPickToPause = { id ->
                path = null
                viewModel.pauseGoalAndRetry(id)
            },
            onStashAsBacklog = {
                path = null
                viewModel.stashAsBacklog()
            },
            onDismiss = { viewModel.cancelLimitHit() },
        )
    }

    when (path) {
        NewGoalPath.QUICK -> QuickGoalSheet(
            onDismiss = { path = null },
            onCreate = { req ->
                viewModel.createGoal(req) { goal ->
                    path = null
                    onGoalClicked(goal.id)
                }
            },
        )
        NewGoalPath.PLAN -> NewGoalWizard(
            onDismiss = { path = null },
            onPlan = { wish, deadline, cb, errCb ->
                viewModel.planGoal(wish, deadline, cb, errCb)
            },
            onAccept = { plan ->
                viewModel.applyPlan(plan) { goalId ->
                    path = null
                    onGoalClicked(goalId)
                }
            },
        )
        NewGoalPath.TALK, null -> Unit
    }
}

internal enum class NewGoalPath { QUICK, PLAN, TALK }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ActiveGoalLimitDialog(
    message: String,
    activeGoals: List<Goal>,
    onPickToPause: (Int) -> Unit,
    onStashAsBacklog: () -> Unit,
    onDismiss: () -> Unit,
) {
    androidx.compose.material3.AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Active goal limit") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(message, style = MaterialTheme.typography.bodyMedium)
                Text(
                    "Pick one to pause and free a slot, or stash this idea in the backlog.",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                activeGoals.forEach { g ->
                    Card(
                        onClick = { onPickToPause(g.id) },
                        shape = androidx.compose.foundation.shape.RoundedCornerShape(10.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surfaceVariant,
                        ),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(modifier = Modifier.padding(10.dp)) {
                            Text(
                                "Pause: ${g.statement}",
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Text(
                                "Priority ${g.priority}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onStashAsBacklog) { Text("Stash in backlog") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}

@Composable
private fun GoalCard(goal: Goal, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "P${goal.priority}",
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelMedium,
                    modifier = Modifier.padding(end = 6.dp),
                )
                Text(
                    text = goal.statement,
                    color = MaterialTheme.colorScheme.onSurface,
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = goal.state,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.labelMedium,
                )
            }
            if (goal.paceTargetAmount > 0.0) {
                Spacer(Modifier.height(6.dp))
                Text(
                    text = "Pace: ${formatNumber(goal.paceTargetAmount)} ${goal.paceTargetUnit}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.labelMedium,
                )
            }
            goal.deadline?.let {
                Spacer(Modifier.height(2.dp))
                Text(
                    text = "Deadline: $it",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.labelMedium,
                )
            }
        }
    }
}

@Composable
private fun SectionLabel(title: String, hint: String?) {
    Column {
        Text(
            title,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
        hint?.let {
            Text(
                it,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private fun formatNumber(d: Double): String {
    return if (d == d.toLong().toDouble()) d.toLong().toString() else "%.2f".format(d)
}

/**
 * Two-step goal wizard. The user types one sentence + an optional date.
 * The backend planner turns that into a full plan (pace target, no-zero
 * floor, milestones, first-week tasks, if-then plans, intervention
 * ceiling). The user reviews in plain English and accepts in one tap.
 * No technical fields ever appear unless the user expands "Advanced".
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NewGoalWizard(
    onDismiss: () -> Unit,
    onPlan: (
        wish: String,
        deadline: String?,
        cb: (com.buddy.app.data.GoalPlan) -> Unit,
        errCb: (String) -> Unit,
    ) -> Unit,
    onAccept: (com.buddy.app.data.GoalPlan) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var wish by remember { mutableStateOf("") }
    var deadline by remember { mutableStateOf<java.time.LocalDate?>(null) }
    var showDeadlinePicker by remember { mutableStateOf(false) }
    var planning by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var plan by remember { mutableStateOf<com.buddy.app.data.GoalPlan?>(null) }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp)
                .padding(bottom = 24.dp)
                .imePadding()
                .navigationBarsPadding(),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            if (plan == null) {
                WishStep(
                    wish = wish,
                    onWishChange = { wish = it },
                    deadline = deadline,
                    onPickDeadline = { showDeadlinePicker = true },
                    onClearDeadline = { deadline = null },
                    planning = planning,
                    error = error,
                    onCancel = onDismiss,
                    onPlan = {
                        if (wish.isBlank()) return@WishStep
                        planning = true
                        error = null
                        onPlan(
                            wish.trim(),
                            deadline?.toString(),
                            { result ->
                                planning = false
                                plan = result
                            },
                            { msg ->
                                planning = false
                                error = msg
                            },
                        )
                    },
                )
            } else {
                PlanReview(
                    plan = plan!!,
                    onBack = { plan = null },
                    onAccept = { onAccept(plan!!) },
                )
            }
        }
    }

    if (showDeadlinePicker) {
        // Material3's DatePicker stores the selected day as UTC
        // midnight. Round-tripping through systemDefault() pushes the
        // value backwards by your timezone offset (so a CST user
        // picking Apr 28 reads back as Apr 27). Use UTC on both sides
        // and the date the user tapped is the date you get.
        val pickerState = rememberDatePickerState(
            initialSelectedDateMillis = deadline
                ?.atStartOfDay(java.time.ZoneOffset.UTC)
                ?.toInstant()?.toEpochMilli()
        )
        DatePickerDialog(
            onDismissRequest = { showDeadlinePicker = false },
            confirmButton = {
                TextButton(onClick = {
                    pickerState.selectedDateMillis?.let { ms ->
                        deadline = java.time.Instant.ofEpochMilli(ms)
                            .atZone(java.time.ZoneOffset.UTC).toLocalDate()
                    }
                    showDeadlinePicker = false
                }) { Text("OK") }
            },
            dismissButton = {
                TextButton(onClick = { showDeadlinePicker = false }) { Text("Cancel") }
            },
        ) {
            DatePicker(state = pickerState)
        }
    }
}

@Composable
private fun WishStep(
    wish: String,
    onWishChange: (String) -> Unit,
    deadline: java.time.LocalDate?,
    onPickDeadline: () -> Unit,
    onClearDeadline: () -> Unit,
    planning: Boolean,
    error: String?,
    onCancel: () -> Unit,
    onPlan: () -> Unit,
) {
    Text(
        "New goal",
        style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Text(
        "Say what you want. I'll handle the rest.",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )

    OutlinedTextField(
        value = wish,
        onValueChange = onWishChange,
        label = { Text("Goal") },
        placeholder = { Text("e.g. read 12 books this year") },
        modifier = Modifier.fillMaxWidth(),
        enabled = !planning,
    )

    androidx.compose.material3.OutlinedButton(
        onClick = onPickDeadline,
        modifier = Modifier.fillMaxWidth(),
        enabled = !planning,
    ) {
        Text(deadline?.let { "By: $it" } ?: "Pick a target date (optional)")
    }
    if (deadline != null) {
        TextButton(onClick = onClearDeadline) {
            Text("Clear date")
        }
    }

    if (error != null) {
        Text(
            error,
            color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.bodyMedium,
        )
    }

    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        androidx.compose.material3.OutlinedButton(
            onClick = onCancel,
            modifier = Modifier.weight(1f),
            enabled = !planning,
        ) { Text("Cancel") }
        androidx.compose.material3.Button(
            onClick = onPlan,
            enabled = !planning && wish.isNotBlank(),
            modifier = Modifier.weight(1f),
        ) {
            if (planning) {
                androidx.compose.material3.CircularProgressIndicator(
                    strokeWidth = 2.dp,
                    modifier = Modifier.size(16.dp),
                    color = MaterialTheme.colorScheme.onPrimary,
                )
            } else {
                Text("Plan it")
            }
        }
    }
    if (planning) {
        Text(
            "Thinking through pace, milestones, and a first-week plan…",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun PlanReview(
    plan: com.buddy.app.data.GoalPlan,
    onBack: () -> Unit,
    onAccept: () -> Unit,
) {
    var showAdvanced by remember { mutableStateOf(false) }

    Text(
        plan.statement,
        style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    if (plan.userFacingSummary.isNotBlank()) {
        Text(
            plan.userFacingSummary,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }

    PlanSection(title = "Pace") {
        val paceLine = if (plan.paceTargetDescription.isNotBlank()) {
            plan.paceTargetDescription
        } else {
            "${formatNumber(plan.paceTargetAmount)} ${plan.paceTargetUnit}"
        }
        Text(paceLine, style = MaterialTheme.typography.bodyLarge)
        if (plan.mvpThreshold.isNotBlank()) {
            Text(
                "Smallest win: ${plan.mvpThreshold}",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }

    if (plan.firstWeekTasks.isNotEmpty()) {
        PlanSection(title = "First steps") {
            plan.firstWeekTasks.forEachIndexed { i, t ->
                Text(
                    "${i + 1}. ${t.description}" +
                        (t.estimatedDurationMinutes?.let { " · ${it}m" } ?: ""),
                    style = MaterialTheme.typography.bodyMedium,
                )
                if (t.first60Seconds.isNotBlank()) {
                    Text(
                        "    start with: ${t.first60Seconds}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }

    if (plan.milestones.isNotEmpty()) {
        PlanSection(title = "Milestones") {
            plan.milestones.forEach { m ->
                val deadlineLabel = m.deadline?.let { " (by $it)" } ?: ""
                Text("• ${m.statement}$deadlineLabel", style = MaterialTheme.typography.bodyMedium)
            }
        }
    }

    if (plan.implementationIntentions.isNotEmpty()) {
        PlanSection(title = "If-then plans") {
            plan.implementationIntentions.forEach { i ->
                Text(
                    "if ${i.cueText} → then ${i.responseText}",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }

    if (plan.obstacles.isNotEmpty()) {
        PlanSection(title = "Obstacles to watch") {
            plan.obstacles.forEach { o ->
                Text("• $o", style = MaterialTheme.typography.bodyMedium)
            }
        }
    }

    HorizontalDivider()

    TextButton(onClick = { showAdvanced = !showAdvanced }) {
        Text(if (showAdvanced) "Hide technical settings" else "Show technical settings")
    }
    if (showAdvanced) {
        Card(
            shape = androidx.compose.foundation.shape.RoundedCornerShape(10.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                val approachLabel = when (plan.approach) {
                    "user_driven" -> "I drive this"
                    "system_assisted" -> "Coach pushes"
                    "hybrid" -> "We work on it together"
                    else -> plan.approach.replace('_', ' ')
                }
                val priorityLabel = when (plan.priority) {
                    1 -> "Low priority"
                    2 -> "Low-mid priority"
                    3 -> "Medium priority"
                    4 -> "High priority"
                    5 -> "Top priority"
                    else -> "Priority ${plan.priority}"
                }
                val nudgeLabel = when (plan.interventionCeiling) {
                    0 -> "Quiet — no nudges"
                    1 -> "Gentle nudges"
                    2 -> "Active nudges"
                    3 -> "Directive — friction overlays"
                    4 -> "Strict — hard blocks"
                    else -> "Nudge level ${plan.interventionCeiling}"
                }
                Text(approachLabel, style = MaterialTheme.typography.labelMedium)
                Text(priorityLabel, style = MaterialTheme.typography.labelMedium)
                Text(nudgeLabel, style = MaterialTheme.typography.labelMedium)
                if (plan.deadline != null) {
                    Text("Deadline: ${plan.deadline}", style = MaterialTheme.typography.labelMedium)
                }
                if (plan.outcomeVision.isNotBlank()) {
                    Text("Outcome: ${plan.outcomeVision}", style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }

    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        androidx.compose.material3.OutlinedButton(
            onClick = onBack,
            modifier = Modifier.weight(1f),
        ) { Text("Edit goal") }
        androidx.compose.material3.Button(
            onClick = onAccept,
            modifier = Modifier.weight(1f),
        ) { Text("Save plan") }
    }
}

/**
 * Three-path chooser per spec §43.2:
 *   QUICK  — "I have a plan, just track this for me." 30-60s.
 *   PLAN   — "Help me plan this." WOOP via the AI planner.
 *   TALK   — "I'm not sure yet, help me figure it out." Opens chat.
 *
 * Default path is QUICK because most goals don't need the full WOOP
 * machinery. The chooser surfaces all three with equal weight so the
 * user picks based on what they actually need that day.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NewGoalPathChooserSheet(
    onDismiss: () -> Unit,
    onChoose: (NewGoalPath) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .padding(bottom = 24.dp)
                .navigationBarsPadding(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                "New goal",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                "How much help do you want with this one?",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            PathCard(
                title = "Just track this",
                subtitle = "I know what I want. Save it and get out of my way.",
                onClick = { onChoose(NewGoalPath.QUICK) },
            )
            PathCard(
                title = "Help me plan it",
                subtitle = "Build out pace, milestones, and if-then plans with me.",
                onClick = { onChoose(NewGoalPath.PLAN) },
            )
            PathCard(
                title = "Not sure yet — let's talk",
                subtitle = "Open the Coach chat and think it through.",
                onClick = { onChoose(NewGoalPath.TALK) },
            )
        }
    }
}

@Composable
private fun PathCard(title: String, subtitle: String, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        shape = androidx.compose.foundation.shape.RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(
                subtitle,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * Path A — quick track-only goal. Goal statement is the only required
 * field; everything else has a sensible default and is reachable from
 * goal detail later. Spec §43.3 calls for three priority dots
 * (low / med / high), so that's what we render. Pace + smallest-win
 * are surfaced behind a single "Add a pace target" disclosure so the
 * default sheet stays under-the-fold-free.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun QuickGoalSheet(
    onDismiss: () -> Unit,
    onCreate: (com.buddy.app.data.GoalCreate) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var statement by remember { mutableStateOf("") }
    var paceAmount by remember { mutableStateOf("") }
    var paceUnit by remember { mutableStateOf("") }
    var mvp by remember { mutableStateOf("") }
    // Three buckets per spec: 2 = low, 3 = medium, 4 = high.
    var priority by remember { mutableStateOf(3) }
    var showPace by remember { mutableStateOf(false) }
    val focusRequester = remember { androidx.compose.ui.focus.FocusRequester() }
    LaunchedEffect(Unit) {
        // Open the sheet ready to type. ADHD-tax avoidance.
        focusRequester.requestFocus()
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        containerColor = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp)
                .padding(bottom = 24.dp)
                .imePadding()
                .navigationBarsPadding(),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    "Just track this",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Text(
                    "One line is enough. You can refine later.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            OutlinedTextField(
                value = statement,
                onValueChange = { statement = it },
                placeholder = { Text("e.g. read 24 books this year") },
                modifier = Modifier
                    .fillMaxWidth()
                    .focusRequester(focusRequester),
            )

            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                listOf(2 to "Low", 3 to "Medium", 4 to "High").forEach { (n, label) ->
                    FilterChip(
                        selected = priority == n,
                        onClick = { priority = n },
                        label = { Text(label) },
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            if (!showPace) {
                androidx.compose.material3.TextButton(onClick = { showPace = true }) {
                    Text("Add a pace target  +")
                }
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "Pace target",
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = paceAmount,
                            onValueChange = {
                                paceAmount = it.filter { ch -> ch.isDigit() || ch == '.' }
                            },
                            label = { Text("Per day") },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                        )
                        OutlinedTextField(
                            value = paceUnit,
                            onValueChange = { paceUnit = it },
                            label = { Text("Unit") },
                            placeholder = { Text("pages…") },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                        )
                    }
                    OutlinedTextField(
                        value = mvp,
                        onValueChange = { mvp = it },
                        label = { Text("Smallest win that still counts") },
                        placeholder = { Text("e.g. 5 pages, 10-min walk") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                androidx.compose.material3.OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                ) { Text("Cancel") }
                androidx.compose.material3.Button(
                    onClick = {
                        if (statement.isBlank()) return@Button
                        onCreate(
                            com.buddy.app.data.GoalCreate(
                                statement = statement.trim(),
                                priority = priority,
                                paceTargetAmount = paceAmount.toDoubleOrNull() ?: 0.0,
                                paceTargetUnit = paceUnit.trim(),
                                mvpThreshold = mvp.trim(),
                            )
                        )
                    },
                    enabled = statement.isNotBlank(),
                    modifier = Modifier.weight(1f),
                ) { Text("Save goal") }
            }
        }
    }
}

@Composable
private fun PlanSection(title: String, content: @Composable () -> Unit) {
    Card(
        shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            content()
        }
    }
}

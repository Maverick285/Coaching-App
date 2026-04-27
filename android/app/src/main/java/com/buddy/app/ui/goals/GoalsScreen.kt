package com.buddy.app.ui.goals

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
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
    viewModel: GoalsViewModel = viewModel(
        factory = GoalsViewModel.factory(LocalContext.current.applicationContext as Application)
    ),
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    var showAdd by remember { mutableStateOf(false) }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbar.showSnackbar(it)
            viewModel.onClearError()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Goals") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    titleContentColor = MaterialTheme.colorScheme.onBackground,
                ),
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { showAdd = true }) {
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

    if (showAdd) {
        NewGoalSheet(
            onDismiss = { showAdd = false },
            onCreate = { req ->
                viewModel.createGoal(req)
                showAdd = false
            },
            onWoop = { wish, obstacle, unit, cb ->
                viewModel.runWoop(WoopRequest(wish, obstacle, unit), cb)
            },
        )
    }
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

/**
 * Modal sheet for creating a goal. Grouped into Wish / Cadence / Floor /
 * Stakes / Help — the sections map to Locke & Latham's findings: specific
 * difficult goals out-perform vague easy ones; commitment + feedback
 * (the pace + MVP fields) raise odds; implementation intentions (WOOP)
 * close the intention–action gap.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun NewGoalSheet(
    onDismiss: () -> Unit,
    onCreate: (GoalCreate) -> Unit,
    onWoop: (wish: String, obstacle: String?, unit: String?, cb: (WoopResponse) -> Unit) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var statement by remember { mutableStateOf("") }
    var paceUnit by remember { mutableStateOf("") }
    var paceAmount by remember { mutableStateOf("") }
    var paceDescription by remember { mutableStateOf("") }
    var mvp by remember { mutableStateOf("") }
    var priority by remember { mutableStateOf(3) }
    var timeframe by remember { mutableStateOf("open_ended") }
    var deadline by remember { mutableStateOf<LocalDate?>(null) }
    var approach by remember { mutableStateOf("user_driven") }
    var ceiling by remember { mutableStateOf(2) }
    var initialObstacle by remember { mutableStateOf("") }
    var showDeadlinePicker by remember { mutableStateOf(false) }
    var woopRunning by remember { mutableStateOf(false) }
    var woopResult by remember { mutableStateOf<WoopResponse?>(null) }

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
            Text(
                "New goal",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )

            // --- Wish ----------------------------------------------------
            SectionLabel("What do you want?", "Specific beats vague. Slightly hard beats easy.")
            OutlinedTextField(
                value = statement,
                onValueChange = { statement = it },
                placeholder = { Text("e.g. ship Buddy v1 to TestFlight") },
                modifier = Modifier.fillMaxWidth(),
            )

            // --- Cadence -------------------------------------------------
            SectionLabel(
                "Cadence",
                "How much per check-in cycle? Small + repeatable beats heroic + sporadic.",
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = paceAmount,
                    onValueChange = { paceAmount = it.filter { ch -> ch.isDigit() || ch == '.' } },
                    label = { Text("Amount") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                OutlinedTextField(
                    value = paceUnit,
                    onValueChange = { paceUnit = it },
                    label = { Text("Unit") },
                    placeholder = { Text("pages, minutes, reps") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
            }
            OutlinedTextField(
                value = paceDescription,
                onValueChange = { paceDescription = it },
                label = { Text("Or describe it") },
                placeholder = { Text("if a number doesn't fit") },
                modifier = Modifier.fillMaxWidth(),
            )

            // --- No-zero floor ------------------------------------------
            SectionLabel(
                "No-zero floor",
                "The smallest thing that still counts as a 1 — keeps streaks alive on bad days.",
            )
            OutlinedTextField(
                value = mvp,
                onValueChange = { mvp = it },
                placeholder = { Text("e.g. open the file and read one paragraph") },
                modifier = Modifier.fillMaxWidth(),
            )

            // --- Stakes --------------------------------------------------
            SectionLabel("Stakes", "Priority weights this goal in your daily grade.")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(
                    1 to "low",
                    2 to "low-mid",
                    3 to "medium",
                    4 to "high",
                    5 to "top",
                ).forEach { (n, label) ->
                    FilterChip(
                        selected = priority == n,
                        onClick = { priority = n },
                        label = { Text("$n · $label") },
                    )
                }
            }

            SectionLabel("Timeframe", null)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(
                    "open_ended" to "Open-ended",
                    "deadline" to "Deadline",
                    "recurring" to "Recurring",
                ).forEach { (id, label) ->
                    FilterChip(
                        selected = timeframe == id,
                        onClick = { timeframe = id },
                        label = { Text(label) },
                    )
                }
            }
            if (timeframe == "deadline") {
                OutlinedButton(
                    onClick = { showDeadlinePicker = true },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(deadline?.let { "Deadline: $it" } ?: "Pick deadline")
                }
            }

            SectionLabel(
                "Coaching tone",
                "How much should the persona drive vs. follow on this one?",
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(
                    "user_driven" to "I drive",
                    "hybrid" to "Hybrid",
                    "system_assisted" to "Push me",
                ).forEach { (id, label) ->
                    FilterChip(
                        selected = approach == id,
                        onClick = { approach = id },
                        label = { Text(label) },
                    )
                }
            }

            SectionLabel(
                "Intervention ceiling",
                "How aggressive can interventions get for this goal? Tier 0 = ambient, 4 = hard-block.",
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                (0..4).forEach { n ->
                    FilterChip(
                        selected = ceiling == n,
                        onClick = { ceiling = n },
                        label = { Text("T$n") },
                    )
                }
            }

            HorizontalDivider()

            // --- Help me plan (WOOP) ------------------------------------
            SectionLabel(
                "Help me plan",
                "Optional. Run WOOP — I'll suggest pace, obstacles, and if-then plans you can accept.",
            )
            OutlinedTextField(
                value = initialObstacle,
                onValueChange = { initialObstacle = it },
                label = { Text("Biggest obstacle (optional)") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedButton(
                onClick = {
                    if (statement.isBlank()) return@OutlinedButton
                    woopRunning = true
                    onWoop(
                        statement.trim(),
                        initialObstacle.trim().takeIf { it.isNotEmpty() },
                        paceUnit.trim().takeIf { it.isNotEmpty() },
                    ) { resp ->
                        woopRunning = false
                        woopResult = resp
                        if (paceUnit.isBlank()) paceUnit = resp.suggestedPaceUnit
                        if (paceAmount.isBlank() && resp.suggestedPaceAmount > 0.0) {
                            paceAmount = formatNumber(resp.suggestedPaceAmount)
                        }
                        if (paceDescription.isBlank() && resp.suggestedPaceDescription.isNotBlank()) {
                            paceDescription = resp.suggestedPaceDescription
                        }
                    }
                },
                enabled = !woopRunning && statement.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (woopRunning) {
                    CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.height(16.dp))
                    Spacer(Modifier.height(0.dp))
                    Text("  Thinking…")
                } else {
                    Text("Help me plan this with WOOP")
                }
            }

            woopResult?.let { r ->
                Card(
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant
                    ),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        if (r.outcome.isNotBlank()) Text("Outcome: ${r.outcome}", style = MaterialTheme.typography.bodyMedium)
                        if (r.obstacles.isNotEmpty()) Text("Obstacles: ${r.obstacles.joinToString(" · ")}", style = MaterialTheme.typography.bodyMedium)
                        if (r.plan.isNotEmpty()) Text("Plan: ${r.plan.joinToString(" · ")}", style = MaterialTheme.typography.bodyMedium)
                        if (r.suggestedIntentions.isNotEmpty()) {
                            Text("If-then plans:", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                            r.suggestedIntentions.forEach {
                                Text(" • if ${it.cueText} → then ${it.responseText}", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }

            HorizontalDivider()

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) {
                    Text("Cancel")
                }
                Button(
                    onClick = {
                        if (statement.isBlank()) return@Button
                        val effectiveTimeframe = if (timeframe == "deadline" && deadline == null) {
                            "open_ended"
                        } else timeframe
                        onCreate(
                            GoalCreate(
                                statement = statement.trim(),
                                priority = priority,
                                paceTargetAmount = paceAmount.toDoubleOrNull() ?: 0.0,
                                paceTargetUnit = paceUnit.trim(),
                                paceTargetDescription = paceDescription.trim(),
                                mvpThreshold = mvp.trim(),
                                approach = approach,
                                planSource = if (woopResult != null) "system_plan" else "user_plan",
                                timeframe = effectiveTimeframe,
                                deadline = deadline?.toString(),
                                interventionCeiling = ceiling,
                            )
                        )
                    },
                    enabled = statement.isNotBlank(),
                    modifier = Modifier.weight(1f),
                ) { Text("Create") }
            }
        }
    }

    if (showDeadlinePicker) {
        val pickerState = rememberDatePickerState(
            initialSelectedDateMillis = deadline?.atStartOfDay(ZoneId.systemDefault())
                ?.toInstant()?.toEpochMilli()
        )
        DatePickerDialog(
            onDismissRequest = { showDeadlinePicker = false },
            confirmButton = {
                TextButton(onClick = {
                    pickerState.selectedDateMillis?.let { ms ->
                        deadline = Instant.ofEpochMilli(ms).atZone(ZoneId.systemDefault()).toLocalDate()
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

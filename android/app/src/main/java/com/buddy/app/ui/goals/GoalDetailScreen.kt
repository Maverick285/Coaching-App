package com.buddy.app.ui.goals

import android.app.Application
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
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
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.buddy.app.data.Goal
import com.buddy.app.data.GoalDetail
import com.buddy.app.data.GoalUpdate
import com.buddy.app.data.Task
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GoalDetailScreen(
    goalId: Int,
    onBack: () -> Unit,
    viewModel: GoalDetailViewModel = viewModel(
        factory = GoalDetailViewModel.factory(
            LocalContext.current.applicationContext as Application,
            goalId,
        ),
        key = "goalDetail_$goalId",
    ),
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    var showLog by remember { mutableStateOf(false) }
    var showTask by remember { mutableStateOf(false) }
    var showDistractionDialog by remember { mutableStateOf(false) }
    var showBlockedAppDialog by remember { mutableStateOf(false) }
    var showEdit by remember { mutableStateOf(false) }
    var menuOpen by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbar.showSnackbar(it)
            viewModel.onClearError()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Goal") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { showEdit = true }) {
                        Icon(Icons.Filled.Edit, contentDescription = "Edit goal")
                    }
                    IconButton(onClick = { menuOpen = true }) {
                        Icon(Icons.Filled.MoreVert, contentDescription = "More")
                    }
                    DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                        val currentState = state.detail?.goal?.state
                        if (currentState == "active") {
                            DropdownMenuItem(
                                text = { Text("Pause") },
                                onClick = {
                                    menuOpen = false
                                    viewModel.updateGoal(GoalUpdate(state = "paused"))
                                },
                            )
                        } else if (currentState == "paused") {
                            DropdownMenuItem(
                                text = { Text("Resume") },
                                onClick = {
                                    menuOpen = false
                                    viewModel.updateGoal(GoalUpdate(state = "active"))
                                },
                            )
                        }
                        if (currentState != "completed") {
                            DropdownMenuItem(
                                text = { Text("Mark complete") },
                                onClick = {
                                    menuOpen = false
                                    viewModel.updateGoal(GoalUpdate(state = "completed"))
                                },
                            )
                        }
                        DropdownMenuItem(
                            text = { Text("Delete…") },
                            onClick = {
                                menuOpen = false
                                confirmDelete = true
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
        snackbarHost = { SnackbarHost(snackbar) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        val detail = state.detail
        if (detail == null) {
            Column(modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp)) {
                Text(
                    if (state.loading) "Loading…" else "Not found.",
                    color = MaterialTheme.colorScheme.onBackground,
                )
            }
        } else {
            DetailBody(
                detail = detail,
                rules = state.distractionRules,
                blockedApps = state.blockedApps,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                onLogClicked = { showLog = true },
                onAddTask = { showTask = true },
                onToggleTask = { task -> viewModel.setTaskDone(task.id) },
                onAddDistraction = { showDistractionDialog = true },
                onRemoveDistraction = { id -> viewModel.removeDistractionRule(id) },
                onAddBlockedApp = { showBlockedAppDialog = true },
                onRemoveBlockedApp = { id -> viewModel.removeBlockedApp(id) },
            )
        }
    }

    if (showLog) {
        LogProgressDialog(
            unit = state.detail?.goal?.paceTargetUnit.orEmpty(),
            onDismiss = { showLog = false },
            onSubmit = { units, raw ->
                viewModel.logProgress(units, state.detail?.goal?.paceTargetUnit.orEmpty(), raw)
                showLog = false
            },
        )
    }
    if (showTask) {
        AddTaskDialog(
            onDismiss = { showTask = false },
            onSubmit = { description, durationMinutes, first60 ->
                viewModel.addTask(description, durationMinutes, first60)
                showTask = false
            },
        )
    }
    if (showDistractionDialog) {
        AddDistractionDialog(
            onDismiss = { showDistractionDialog = false },
            onSubmit = { category, cooldown ->
                viewModel.addDistractionRule(category, cooldown)
                showDistractionDialog = false
            },
        )
    }
    if (showBlockedAppDialog) {
        AddBlockedAppDialog(
            onDismiss = { showBlockedAppDialog = false },
            onSubmit = { pkg, tier ->
                viewModel.addBlockedApp(pkg, tier)
                showBlockedAppDialog = false
            },
        )
    }
    if (showEdit) {
        state.detail?.goal?.let { g ->
            EditGoalSheet(
                goal = g,
                onDismiss = { showEdit = false },
                onSave = { update ->
                    viewModel.updateGoal(update)
                    showEdit = false
                },
            )
        }
    }
    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete this goal?") },
            text = { Text("Progress logs and tasks under it will be cleaned up. This can't be undone.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmDelete = false
                    viewModel.deleteGoal { onBack() }
                }) { Text("Delete") }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun EditGoalSheet(
    goal: Goal,
    onDismiss: () -> Unit,
    onSave: (GoalUpdate) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var statement by remember { mutableStateOf(goal.statement) }
    var paceUnit by remember { mutableStateOf(goal.paceTargetUnit) }
    var paceAmount by remember {
        mutableStateOf(if (goal.paceTargetAmount > 0) formatNumber(goal.paceTargetAmount) else "")
    }
    var paceDescription by remember { mutableStateOf(goal.paceTargetDescription) }
    var mvp by remember { mutableStateOf(goal.mvpThreshold) }
    var priority by remember { mutableStateOf(goal.priority) }
    var approach by remember { mutableStateOf(goal.approach) }
    var ceiling by remember { mutableStateOf(goal.interventionCeiling) }

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
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Edit goal", style = MaterialTheme.typography.titleLarge)
            OutlinedTextField(
                value = statement,
                onValueChange = { statement = it },
                label = { Text("Statement") },
                modifier = Modifier.fillMaxWidth(),
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
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
            }
            OutlinedTextField(
                value = paceDescription,
                onValueChange = { paceDescription = it },
                label = { Text("Pace description") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = mvp,
                onValueChange = { mvp = it },
                label = { Text("No-zero floor") },
                modifier = Modifier.fillMaxWidth(),
            )
            Text("Priority", style = MaterialTheme.typography.titleMedium)
            androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                (1..5).forEach { n ->
                    FilterChip(
                        selected = priority == n,
                        onClick = { priority = n },
                        label = { Text("$n") },
                    )
                }
            }
            Text("Coaching tone", style = MaterialTheme.typography.titleMedium)
            androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
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
            Text("Intervention ceiling", style = MaterialTheme.typography.titleMedium)
            androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                (0..4).forEach { n ->
                    FilterChip(
                        selected = ceiling == n,
                        onClick = { ceiling = n },
                        label = { Text("T$n") },
                    )
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) {
                    Text("Cancel")
                }
                Button(
                    onClick = {
                        onSave(
                            GoalUpdate(
                                statement = statement.trim(),
                                priority = priority,
                                paceTargetAmount = paceAmount.toDoubleOrNull() ?: 0.0,
                                paceTargetUnit = paceUnit.trim(),
                                paceTargetDescription = paceDescription.trim(),
                                mvpThreshold = mvp.trim(),
                                approach = approach,
                                interventionCeiling = ceiling,
                            )
                        )
                    },
                    enabled = statement.isNotBlank(),
                    modifier = Modifier.weight(1f),
                ) { Text("Save") }
            }
        }
    }
}

@Composable
private fun DetailBody(
    detail: GoalDetail,
    rules: List<com.buddy.app.data.DistractionRule>,
    blockedApps: List<com.buddy.app.data.BlockedAppRule>,
    modifier: Modifier,
    onLogClicked: () -> Unit,
    onAddTask: () -> Unit,
    onToggleTask: (Task) -> Unit,
    onAddDistraction: () -> Unit,
    onRemoveDistraction: (Int) -> Unit,
    onAddBlockedApp: () -> Unit,
    onRemoveBlockedApp: (Int) -> Unit,
) {
    val goal = detail.goal
    LazyColumn(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            Card(
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Text(
                        text = goal.statement,
                        style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Spacer(Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        // Show plain-English labels instead of the
                        // raw priority integer ("P5") and the raw
                        // approach enum ("user_driven"). Internal
                        // codes belong in the DB, not on the screen.
                        val priorityLabel = when (goal.priority) {
                            1 -> "Low priority"
                            2 -> "Low-mid priority"
                            3 -> "Medium priority"
                            4 -> "High priority"
                            5 -> "Top priority"
                            else -> "Priority ${goal.priority}"
                        }
                        val stateLabel = goal.state.replaceFirstChar { it.uppercase() }
                        val approachLabel = when (goal.approach) {
                            "user_driven" -> "I drive"
                            "system_assisted" -> "Coach pushes"
                            "hybrid" -> "Hybrid"
                            else -> goal.approach.replace('_', ' ')
                                .replaceFirstChar { it.uppercase() }
                        }
                        AssistChip(onClick = {}, label = { Text(priorityLabel) })
                        AssistChip(onClick = {}, label = { Text(stateLabel) })
                        AssistChip(onClick = {}, label = { Text(approachLabel) })
                    }
                    Spacer(Modifier.height(10.dp))
                    if (goal.paceTargetAmount > 0.0) {
                        val ratio = (detail.todayProgress / goal.paceTargetAmount)
                            .coerceAtLeast(0.0)
                        Text(
                            text = "Today: ${formatNumber(detail.todayProgress)} / " +
                                "${formatNumber(goal.paceTargetAmount)} ${goal.paceTargetUnit} " +
                                "(${"%.2f".format(detail.todayGrade)})",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Spacer(Modifier.height(4.dp))
                        LinearProgressIndicator(
                            progress = { ratio.coerceAtMost(1.0).toFloat() },
                            modifier = Modifier.fillMaxWidth(),
                        )
                    } else {
                        Text(
                            text = "No daily pace set.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                    if (goal.mvpThreshold.isNotEmpty()) {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            text = "Counts as a 1: ${goal.mvpThreshold}",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.labelMedium,
                        )
                    }
                    Spacer(Modifier.height(10.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = onLogClicked, modifier = Modifier.weight(1f)) {
                            Text("Log progress")
                        }
                        Button(onClick = onAddTask, modifier = Modifier.weight(1f)) {
                            Text("+ Task")
                        }
                    }
                }
            }
        }

        if (detail.tasks.isNotEmpty()) {
            item {
                Text(
                    "Tasks",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
            items(detail.tasks, key = { it.id }) { t ->
                TaskRow(t, onToggle = { onToggleTask(t) })
            }
        }

        if (detail.intentions.isNotEmpty()) {
            item {
                Text(
                    "Implementation intentions",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
            items(detail.intentions, key = { it.id }) { i ->
                Card(
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(
                            text = i.cueType,
                            color = MaterialTheme.colorScheme.primary,
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            text = "if ${i.cueText} → then ${i.responseText}",
                            color = MaterialTheme.colorScheme.onSurface,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "Distractions",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.weight(1f),
                )
                com.buddy.app.ui.common.InfoTooltip(
                    title = "Distractions",
                    body = "Categories that count as drift during this goal's focus sessions. Tier 0/1/2 nudges fire if you stay in one for the cooldown duration.",
                )
                androidx.compose.material3.TextButton(onClick = onAddDistraction) {
                    Text("+ Add")
                }
            }
        }
        if (rules.isEmpty()) {
            item {
                Text(
                    "(none)",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        } else {
            items(rules, key = { it.id }) { rule ->
                Card(
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = rule.distractorCategory,
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.onSurface,
                                fontWeight = FontWeight.Medium,
                            )
                            Text(
                                text = "${rule.cooldownSeconds}s grace",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        androidx.compose.material3.TextButton(
                            onClick = { onRemoveDistraction(rule.id) }
                        ) { Text("Remove") }
                    }
                }
            }
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "Blocked apps",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.weight(1f),
                )
                com.buddy.app.ui.common.InfoTooltip(
                    title = "Blocked apps",
                    body = "Tier 3 = 60-second friction screen before opening. Tier 4 = redirect to home; override required. Needs accessibility access; grant from Customize.",
                )
                androidx.compose.material3.TextButton(onClick = onAddBlockedApp) {
                    Text("+ Add")
                }
            }
        }
        if (blockedApps.isEmpty()) {
            item {
                Text(
                    "(none)",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        } else {
            items(blockedApps, key = { it.id }) { app ->
                Card(
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = app.packageName,
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.onSurface,
                                fontWeight = FontWeight.Medium,
                            )
                            Text(
                                text = if (app.blockTier == 4) "Tier 4 · hard block" else "Tier 3 · friction",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        androidx.compose.material3.TextButton(
                            onClick = { onRemoveBlockedApp(app.id) }
                        ) { Text("Remove") }
                    }
                }
            }
        }
    }
}

@Composable
private fun TaskRow(task: Task, onToggle: () -> Unit) {
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth().clickable { onToggle() },
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = task.state == "done", onCheckedChange = { onToggle() })
            Spacer(Modifier.height(0.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = task.description,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    textDecoration = if (task.state == "done") TextDecoration.LineThrough else null,
                )
                if (task.first60Seconds.isNotEmpty()) {
                    Text(
                        text = "first 60s: ${task.first60Seconds}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            task.estimatedDurationMinutes?.let {
                Text(
                    text = "${it}m",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LogProgressDialog(
    unit: String,
    onDismiss: () -> Unit,
    onSubmit: (units: Double, rawText: String) -> Unit,
) {
    var amount by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Log progress${if (unit.isNotEmpty()) " ($unit)" else ""}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = amount,
                    onValueChange = { amount = it },
                    label = { Text("Amount") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("Note (optional)") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                amount.toDoubleOrNull()?.let { onSubmit(it, note) }
            }) { Text("Log") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddTaskDialog(
    onDismiss: () -> Unit,
    onSubmit: (description: String, durationMinutes: Int?, first60: String) -> Unit,
) {
    var description by remember { mutableStateOf("") }
    var minutesText by remember { mutableStateOf("") }
    var first60 by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("New task") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("Description") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = minutesText,
                    onValueChange = { minutesText = it.filter { ch -> ch.isDigit() } },
                    label = { Text("Estimated minutes (optional)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = first60,
                    onValueChange = { first60 = it },
                    label = { Text("First 60 seconds (optional)") },
                    placeholder = { Text("e.g. open the file") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                if (description.isNotBlank()) {
                    onSubmit(
                        description.trim(),
                        minutesText.toIntOrNull(),
                        first60.trim(),
                    )
                }
            }) { Text("Add") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

private fun formatNumber(d: Double): String =
    if (d == d.toLong().toDouble()) d.toLong().toString() else "%.2f".format(d)

@OptIn(ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun AddDistractionDialog(
    onDismiss: () -> Unit,
    onSubmit: (category: String, cooldownSeconds: Int) -> Unit,
) {
    val categories = listOf(
        "social_media", "video", "music", "communication",
        "browser", "gaming", "other",
    )
    var selected by remember { mutableStateOf(categories.first()) }
    var cooldownText by remember { mutableStateOf("90") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Add distraction", modifier = Modifier.weight(1f))
                com.buddy.app.ui.common.InfoTooltip(
                    title = "Distraction rule",
                    body = "When this category is foreground for the cooldown duration during a session for this goal, Tier 0 fires.",
                )
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                androidx.compose.foundation.layout.FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    categories.forEach { c ->
                        AssistChip(
                            onClick = { selected = c },
                            label = { Text(c) },
                            colors = if (c == selected) {
                                androidx.compose.material3.AssistChipDefaults.assistChipColors(
                                    containerColor = MaterialTheme.colorScheme.primary,
                                    labelColor = MaterialTheme.colorScheme.onPrimary,
                                )
                            } else androidx.compose.material3.AssistChipDefaults.assistChipColors(),
                        )
                    }
                }
                OutlinedTextField(
                    value = cooldownText,
                    onValueChange = { cooldownText = it.filter { ch -> ch.isDigit() } },
                    label = { Text("Cooldown (seconds, default 90)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                onSubmit(selected, cooldownText.toIntOrNull() ?: 90)
            }) { Text("Add") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddBlockedAppDialog(
    onDismiss: () -> Unit,
    onSubmit: (packageName: String, blockTier: Int) -> Unit,
) {
    var pkg by remember { mutableStateOf("") }
    var tier by remember { mutableStateOf(3) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Block an app", modifier = Modifier.weight(1f))
                com.buddy.app.ui.common.InfoTooltip(
                    title = "Block tiers",
                    body = "Tier 3 = friction (60s pause before opening). Tier 4 = hard block (redirect home; override required). Find package names with: adb shell pm list packages | grep <vendor>.",
                )
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = pkg,
                    onValueChange = { pkg = it.trim() },
                    label = { Text("Package name") },
                    placeholder = { Text("e.g. com.twitter.android") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    AssistChip(
                        onClick = { tier = 3 },
                        label = { Text("Tier 3 friction") },
                        colors = if (tier == 3) {
                            androidx.compose.material3.AssistChipDefaults.assistChipColors(
                                containerColor = MaterialTheme.colorScheme.primary,
                                labelColor = MaterialTheme.colorScheme.onPrimary,
                            )
                        } else androidx.compose.material3.AssistChipDefaults.assistChipColors(),
                    )
                    AssistChip(
                        onClick = { tier = 4 },
                        label = { Text("Tier 4 hard block") },
                        colors = if (tier == 4) {
                            androidx.compose.material3.AssistChipDefaults.assistChipColors(
                                containerColor = MaterialTheme.colorScheme.primary,
                                labelColor = MaterialTheme.colorScheme.onPrimary,
                            )
                        } else androidx.compose.material3.AssistChipDefaults.assistChipColors(),
                    )
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { if (pkg.isNotBlank()) onSubmit(pkg, tier) },
            ) { Text("Add") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

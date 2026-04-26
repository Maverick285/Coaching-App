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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import com.buddy.app.data.GoalDetail
import com.buddy.app.data.Task

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
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                onLogClicked = { showLog = true },
                onAddTask = { showTask = true },
                onToggleTask = { task -> viewModel.setTaskDone(task.id) },
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
}

@Composable
private fun DetailBody(
    detail: GoalDetail,
    modifier: Modifier,
    onLogClicked: () -> Unit,
    onAddTask: () -> Unit,
    onToggleTask: (Task) -> Unit,
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
                        AssistChip(onClick = {}, label = { Text("P${goal.priority}") })
                        AssistChip(onClick = {}, label = { Text(goal.state) })
                        AssistChip(onClick = {}, label = { Text(goal.approach) })
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

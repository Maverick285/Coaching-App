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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.buddy.app.data.Goal
import com.buddy.app.data.GoalCreate

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
                Row(
                    modifier = Modifier
                        .fillMaxSize(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center,
                ) {
                    CircularProgressIndicator()
                }
            } else if (state.goals.isEmpty()) {
                Text(
                    "No goals yet. Tap + to add one (or use `buddy goal woop` from the CLI for an assisted plan).",
                    modifier = Modifier.padding(24.dp),
                    color = MaterialTheme.colorScheme.onBackground,
                )
            } else {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
                ) {
                    items(state.goals, key = { it.id }) { goal ->
                        GoalCard(goal, onClick = { onGoalClicked(goal.id) })
                    }
                }
            }
        }
    }

    if (showAdd) {
        AddGoalDialog(
            onDismiss = { showAdd = false },
            onCreate = { req ->
                viewModel.createGoal(req)
                showAdd = false
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
                    modifier = Modifier
                        .clickable {}
                        .padding(end = 6.dp),
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
                    text = "Pace: ${formatNumber(goal.paceTargetAmount)} ${goal.paceTargetUnit} / day",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.labelMedium,
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddGoalDialog(onDismiss: () -> Unit, onCreate: (GoalCreate) -> Unit) {
    var statement by remember { mutableStateOf("") }
    var paceUnit by remember { mutableStateOf("") }
    var paceAmountText by remember { mutableStateOf("") }
    var priorityText by remember { mutableStateOf("3") }
    var mvp by remember { mutableStateOf("") }

    androidx.compose.material3.AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("New goal") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                androidx.compose.material3.OutlinedTextField(
                    value = statement,
                    onValueChange = { statement = it },
                    label = { Text("Statement") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    androidx.compose.material3.OutlinedTextField(
                        value = paceAmountText,
                        onValueChange = { paceAmountText = it },
                        label = { Text("Daily target") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                    )
                    androidx.compose.material3.OutlinedTextField(
                        value = paceUnit,
                        onValueChange = { paceUnit = it },
                        label = { Text("Unit") },
                        placeholder = { Text("pages, minutes…") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                    )
                }
                androidx.compose.material3.OutlinedTextField(
                    value = priorityText,
                    onValueChange = {
                        priorityText = it.filter { ch -> ch.isDigit() }.take(1)
                    },
                    label = { Text("Priority (1-5)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                androidx.compose.material3.OutlinedTextField(
                    value = mvp,
                    onValueChange = { mvp = it },
                    label = { Text("Minimum that counts as a 1") },
                    placeholder = { Text("e.g. 1 page") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            androidx.compose.material3.TextButton(onClick = {
                if (statement.isNotBlank()) {
                    onCreate(
                        GoalCreate(
                            statement = statement.trim(),
                            priority = priorityText.toIntOrNull()?.coerceIn(1, 5) ?: 3,
                            paceTargetAmount = paceAmountText.toDoubleOrNull() ?: 0.0,
                            paceTargetUnit = paceUnit.trim(),
                            mvpThreshold = mvp.trim(),
                        )
                    )
                }
            }) { Text("Create") }
        },
        dismissButton = {
            androidx.compose.material3.TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}

private fun formatNumber(d: Double): String {
    return if (d == d.toLong().toDouble()) d.toLong().toString() else "%.2f".format(d)
}

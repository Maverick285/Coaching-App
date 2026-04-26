package com.buddy.app.focus

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.buddy.app.R
import com.buddy.app.data.FocusSession
import com.buddy.app.data.Goal
import java.time.Duration
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FocusScreen(
    viewModel: FocusViewModel = viewModel(
        factory = FocusViewModel.factory(LocalContext.current.applicationContext as Application)
    ),
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbar.showSnackbar(it)
            viewModel.onClearError()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.title_focus)) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    titleContentColor = MaterialTheme.colorScheme.onBackground,
                ),
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        if (!state.configured) {
            Text(
                "Configure backend in Settings first.",
                modifier = Modifier.padding(24.dp),
                color = MaterialTheme.colorScheme.onBackground,
            )
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                if (state.active != null) {
                    ActiveSessionCard(
                        session = state.active!!,
                        ending = state.ending,
                        onEnd = viewModel::end,
                    )
                } else {
                    StartSessionCard(
                        intention = state.intention,
                        minutes = state.plannedMinutes,
                        starting = state.starting,
                        goals = state.goals,
                        selectedGoalId = state.selectedGoalId,
                        onIntentionChange = viewModel::setIntention,
                        onMinutesChange = viewModel::setMinutes,
                        onSelectGoal = viewModel::setGoal,
                        onStart = viewModel::start,
                    )
                }
            }
            if (state.recent.isNotEmpty()) {
                item {
                    Text(
                        "Recent sessions",
                        style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onBackground,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
                items(state.recent.filter { it.state != "active" }, key = { it.id }) { s ->
                    RecentRow(s)
                }
            }
        }
    }
}

@Composable
private fun ActiveSessionCard(
    session: FocusSession,
    ending: Boolean,
    onEnd: (String) -> Unit,
) {
    Card(
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Text(
                "Active session",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.height(6.dp))
            Text(
                text = session.intention,
                style = MaterialTheme.typography.headlineSmall,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "${session.plannedDurationMinutes} minutes  ·  started ${formatTimeOnly(session.startedAt)}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = { onEnd("") },
                modifier = Modifier.fillMaxWidth(),
                enabled = !ending,
            ) {
                if (ending) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.size(6.dp))
                }
                Text(stringResource(R.string.action_end_focus))
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StartSessionCard(
    intention: String,
    minutes: Int,
    starting: Boolean,
    goals: List<Goal>,
    selectedGoalId: Int?,
    onIntentionChange: (String) -> Unit,
    onMinutesChange: (Int) -> Unit,
    onSelectGoal: (Int?) -> Unit,
    onStart: () -> Unit,
) {
    Card(
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Text(
                "Set an intention",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(
                value = intention,
                onValueChange = onIntentionChange,
                placeholder = { Text(stringResource(R.string.hint_focus_intention)) },
                modifier = Modifier.fillMaxWidth(),
                maxLines = 3,
            )
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(
                value = minutes.toString(),
                onValueChange = { onMinutesChange(it.toIntOrNull() ?: minutes) },
                label = { Text("Minutes") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
            )
            if (goals.isNotEmpty()) {
                Spacer(Modifier.height(10.dp))
                Text(
                    "Goal (optional)",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(4.dp))
                Box(modifier = Modifier.fillMaxWidth()) {
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        AssistChip(
                            onClick = { onSelectGoal(null) },
                            label = { Text("none") },
                            colors = if (selectedGoalId == null) selectedChipColors() else AssistChipDefaults.assistChipColors(),
                        )
                        goals.forEach { g ->
                            AssistChip(
                                onClick = { onSelectGoal(g.id) },
                                label = { Text(g.statement.take(20)) },
                                colors = if (selectedGoalId == g.id) selectedChipColors() else AssistChipDefaults.assistChipColors(),
                            )
                        }
                    }
                }
            }
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = onStart,
                modifier = Modifier.fillMaxWidth(),
                enabled = !starting && intention.isNotBlank(),
            ) {
                if (starting) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.size(6.dp))
                }
                Text(stringResource(R.string.action_start_focus))
            }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = { /* no-op for now; intentionally bare */ },
                modifier = Modifier.fillMaxWidth(),
                enabled = false,
            ) {
                Text("Body-doubling check-ins are automatic.")
            }
        }
    }
}

@Composable
private fun selectedChipColors() = AssistChipDefaults.assistChipColors(
    containerColor = MaterialTheme.colorScheme.primary,
    labelColor = MaterialTheme.colorScheme.onPrimary,
)

@Composable
private fun RecentRow(session: FocusSession) {
    val durationText = if (session.endedAt != null) {
        try {
            val start = OffsetDateTime.parse(session.startedAt)
            val end = OffsetDateTime.parse(session.endedAt)
            "${Duration.between(start, end).toMinutes()} min"
        } catch (_: Exception) {
            "${session.plannedDurationMinutes} min"
        }
    } else {
        "${session.plannedDurationMinutes} min"
    }

    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = session.intention,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Text(
                    text = "${formatDateTime(session.startedAt)}  ·  $durationText  ·  ${session.state}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

private fun formatDateTime(iso: String): String = try {
    OffsetDateTime.parse(iso).format(DateTimeFormatter.ofPattern("MMM d, HH:mm"))
} catch (_: Exception) {
    iso
}

private fun formatTimeOnly(iso: String): String = try {
    OffsetDateTime.parse(iso).format(DateTimeFormatter.ofPattern("HH:mm"))
} catch (_: Exception) {
    iso
}

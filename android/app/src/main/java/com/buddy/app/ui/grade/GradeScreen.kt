package com.buddy.app.ui.grade

import android.app.Application
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.buddy.app.data.DayGrade
import com.buddy.app.data.PerGoalGrade
import com.buddy.app.data.StreakResponse
import com.buddy.app.data.WeeklyReviewResponse

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GradeScreen(
    viewModel: GradeViewModel = viewModel(
        factory = GradeViewModel.factory(LocalContext.current.applicationContext as Application)
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
                title = { Text("Grade") },
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
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item { GradeCard(state.grade, state.loading, viewModel::finalize) }
                state.streak?.let { streak ->
                    item { StreakCard(streak) }
                }
                state.grade?.perGoal?.let { perGoal ->
                    if (perGoal.isNotEmpty()) {
                        item {
                            Text(
                                "Per-goal",
                                style = MaterialTheme.typography.titleLarge,
                                color = MaterialTheme.colorScheme.onBackground,
                                modifier = Modifier.padding(top = 6.dp),
                            )
                        }
                        items(perGoal) { p -> PerGoalRow(p) }
                    }
                }
                item {
                    WeeklyReviewSection(
                        weekly = state.weekly,
                        loading = state.weeklyLoading,
                        onRun = viewModel::fetchWeeklyReview,
                    )
                }
            }
        }
    }
}

@Composable
private fun GradeCard(
    grade: DayGrade?,
    loading: Boolean,
    onFinalize: (acceptSystem: Boolean, userScore: Double?, notes: String) -> Unit,
) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            if (grade == null) {
                Text(
                    if (loading) "Computing today's grade…" else "No grade yet.",
                    color = MaterialTheme.colorScheme.onSurface,
                )
                return@Card
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                ScorePill(score = grade.userScore ?: grade.systemScore, isZero = grade.isZeroDay)
                Spacer(Modifier.size(16.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = if (grade.isZeroDay) "Zero day" else "Today's score",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = grade.gradeDate,
                        style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                }
            }
            if (grade.explanation.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    text = grade.explanation,
                    color = MaterialTheme.colorScheme.onSurface,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            Spacer(Modifier.height(12.dp))
            if (grade.finalized) {
                Text(
                    "Finalized" + (grade.userNotes.takeIf { it.isNotEmpty() }?.let { " · $it" } ?: ""),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                FinalizeRow(onFinalize)
            }
        }
    }
}

@Composable
private fun FinalizeRow(
    onFinalize: (acceptSystem: Boolean, userScore: Double?, notes: String) -> Unit,
) {
    var showAdjust by remember { mutableStateOf(false) }
    var customScoreText by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = { onFinalize(true, null, notes) },
                modifier = Modifier.weight(1f),
            ) { Text("Accept") }
            OutlinedButton(
                onClick = { showAdjust = !showAdjust },
                modifier = Modifier.weight(1f),
            ) { Text(if (showAdjust) "Cancel adjust" else "Adjust") }
        }
        if (showAdjust) {
            OutlinedTextField(
                value = customScoreText,
                onValueChange = { customScoreText = it },
                label = { Text("Your score (e.g. 1.20)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = notes,
                onValueChange = { notes = it },
                label = { Text("Notes") },
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = {
                    onFinalize(false, customScoreText.toDoubleOrNull(), notes)
                    showAdjust = false
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Save adjusted score") }
        }
    }
}

@Composable
private fun ScorePill(score: Double, isZero: Boolean) {
    val bg = when {
        isZero -> MaterialTheme.colorScheme.error
        score >= 1.0 -> MaterialTheme.colorScheme.primary
        score > 0.0 -> MaterialTheme.colorScheme.surfaceVariant
        else -> MaterialTheme.colorScheme.error
    }
    Box(
        modifier = Modifier
            .size(72.dp)
            .background(bg, CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "%.2f".format(score),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onPrimary,
        )
    }
}

@Composable
private fun PerGoalRow(p: PerGoalGrade) {
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row {
                Text(
                    text = p.statement,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = "%.2f".format(p.score),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
            Spacer(Modifier.height(4.dp))
            Text(
                text = "${formatNumber(p.progressToday)} / ${formatNumber(p.paceTargetAmount)} ${p.paceTargetUnit}",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(4.dp))
            LinearProgressIndicator(
                progress = { (p.score.coerceIn(0.0, 1.0)).toFloat() },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun StreakCard(streak: StreakResponse) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(
                text = "Streak: ${streak.currentStreakLength} days",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                streak.history.takeLast(28).forEach { d ->
                    val color = when {
                        d.isPause -> Color.Gray.copy(alpha = 0.4f)
                        d.isZero -> MaterialTheme.colorScheme.error
                        d.score >= 1.0 -> MaterialTheme.colorScheme.primary
                        else -> MaterialTheme.colorScheme.surfaceVariant
                    }
                    Box(
                        modifier = Modifier
                            .size(12.dp)
                            .background(color, RoundedCornerShape(2.dp))
                    )
                }
            }
            Spacer(Modifier.height(6.dp))
            Text(
                text = "Last 28 days. Gray = pause, red = zero, blue = ≥ par 1.0.",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun WeeklyReviewSection(
    weekly: WeeklyReviewResponse?,
    loading: Boolean,
    onRun: () -> Unit,
) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "Weekly review",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(1f),
                )
                if (loading) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp,
                        modifier = Modifier.size(20.dp),
                    )
                } else {
                    Button(onClick = onRun) { Text(if (weekly == null) "Run" else "Refresh") }
                }
            }
            if (weekly != null) {
                Spacer(Modifier.height(6.dp))
                Text(
                    "${weekly.weekStart} → ${weekly.weekEnd}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "Average: ${"%.2f".format(weekly.averageDayGrade)}",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                if (weekly.patternObservations.isNotEmpty()) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Patterns",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                    )
                    weekly.patternObservations.forEach {
                        Text(
                            "• $it",
                            color = MaterialTheme.colorScheme.onSurface,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
                if (weekly.suggestedAdjustments.isNotEmpty()) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Suggestions",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                    )
                    weekly.suggestedAdjustments.forEach {
                        Text(
                            "• $it",
                            color = MaterialTheme.colorScheme.onSurface,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }
    }
}

private fun formatNumber(d: Double): String =
    if (d == d.toLong().toDouble()) d.toLong().toString() else "%.2f".format(d)

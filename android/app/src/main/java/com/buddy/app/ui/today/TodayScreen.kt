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
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import com.buddy.app.capture.CaptureActivity
import com.buddy.app.data.DailyPlanItem
import com.buddy.app.data.DayGrade
import com.buddy.app.data.Goal
import com.buddy.app.data.StreakResponse

/**
 * Today screen, rebuilt around the "Coach me today" daily plan
 * (master spec §15). On first morning use of a new day, the backend
 * generates a plan: goal-derived tasks tiered Must / Should / Could.
 * Each item is a card with done / later / skip / "tell coach why"
 * actions. Day grade + streak ride along at the top.
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
    var explainItem by remember { mutableStateOf<DailyPlanItem?>(null) }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbar.showSnackbar(it)
            viewModel.onClearError()
        }
    }

    LaunchedEffect(Unit) {
        viewModel.refresh()
        com.buddy.app.data.RefreshBus.goals.collect { viewModel.refresh() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Today") },
                actions = {
                    IconButton(onClick = { menuOpen = true }) {
                        Icon(Icons.Filled.MoreVert, contentDescription = "Menu")
                    }
                    DropdownMenu(
                        expanded = menuOpen,
                        onDismissRequest = { menuOpen = false },
                    ) {
                        DropdownMenuItem(
                            text = { Text("Customize") },
                            onClick = { menuOpen = false; onOpenCustomize() },
                        )
                        DropdownMenuItem(
                            text = { Text("Settings") },
                            onClick = { menuOpen = false; onOpenSettings() },
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
            FloatingActionButton(onClick = {
                context.startActivity(
                    android.content.Intent(context, CaptureActivity::class.java)
                        .putExtra(CaptureActivity.EXTRA_SOURCE, "today_fab")
                )
            }) { Icon(Icons.Filled.GraphicEq, contentDescription = "Quick capture") }
        },
        snackbarHost = { SnackbarHost(snackbar) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        if (!state.configured) {
            Column(modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp)) {
                Text(
                    "Configure backend in Settings first.",
                    color = MaterialTheme.colorScheme.onBackground,
                )
            }
            return@Scaffold
        }
        if (state.loading && state.plan == null) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { CircularProgressIndicator() }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                StatusHeader(grade = state.grade, streak = state.streak)
            }

            val plan = state.plan
            if (plan != null && plan.rationale.isNotBlank()) {
                item {
                    Text(
                        plan.rationale,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onBackground,
                    )
                }
            }

            if (plan == null || plan.items.isEmpty()) {
                item {
                    EmptyPlanCard(
                        hasGoals = state.goalsById.isNotEmpty(),
                        onOpenGoals = onOpenGoals,
                        onOpenChat = onOpenChat,
                    )
                }
            } else {
                val pending = plan.items.filter { it.state == "pending" }
                val finished = plan.items.filter { it.state != "pending" }
                listOf("must", "should", "could").forEach { tier ->
                    val tierItems = pending.filter { it.tier == tier }
                    if (tierItems.isNotEmpty()) {
                        item { TierHeader(tier = tier, count = tierItems.size) }
                        items(tierItems, key = { "p-${it.id}" }) { item ->
                            PlanItemCard(
                                item = item,
                                goal = state.goalsById[item.goalId],
                                saving = item.id in state.savingItemIds,
                                onDone = { viewModel.markDone(item) },
                                onLater = { viewModel.deferUntilLater(item) },
                                onSkip = { viewModel.decline(item) },
                                onExplain = { explainItem = item },
                                onOpenGoal = { onOpenGoalDetail(item.goalId) },
                            )
                        }
                    }
                }
                if (finished.isNotEmpty()) {
                    item { TierHeader(tier = "done", count = finished.size) }
                    items(finished, key = { "f-${it.id}" }) { item ->
                        FinishedItemRow(item = item, goal = state.goalsById[item.goalId])
                    }
                }
            }

            if (state.pendingDreams > 0) {
                item {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "${state.pendingDreams} memory proposal${if (state.pendingDreams == 1) "" else "s"} waiting in Dreams.",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
        }
    }

    explainItem?.let { item ->
        ExplainSheet(
            item = item,
            onDismiss = { explainItem = null },
            onDefer = { reason ->
                viewModel.deferUntilLater(item, reason)
                explainItem = null
            },
            onSkip = { reason ->
                if (reason.isNotBlank()) {
                    // Decline still records the user's reason on the row
                    // for future plan generations to consider.
                    viewModel.deferUntilLater(item, reason)
                } else {
                    viewModel.decline(item)
                }
                explainItem = null
            },
        )
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
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(verticalAlignment = Alignment.Bottom) {
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
private fun TierHeader(tier: String, count: Int) {
    val label = when (tier) {
        "must" -> "Must do"
        "should" -> "Should do"
        "could" -> "Could do"
        "done" -> "Done & dismissed"
        else -> tier
    }
    val color = when (tier) {
        "must" -> MaterialTheme.colorScheme.onBackground
        "done" -> MaterialTheme.colorScheme.onSurfaceVariant
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            label,
            style = MaterialTheme.typography.titleMedium,
            color = color,
            fontWeight = if (tier == "must") FontWeight.SemiBold else FontWeight.Medium,
        )
        Spacer(Modifier.size(8.dp))
        Text(
            count.toString(),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun PlanItemCard(
    item: DailyPlanItem,
    goal: Goal?,
    saving: Boolean,
    onDone: () -> Unit,
    onLater: () -> Unit,
    onSkip: () -> Unit,
    onExplain: () -> Unit,
    onOpenGoal: () -> Unit,
) {
    // Tier-based color treatment per spec §21.2: brightness/saturation
    // gradient, not red/yellow/green. Must = full color. Should =
    // dimmed. Could = muted variant.
    val container = when (item.tier) {
        "must" -> MaterialTheme.colorScheme.surface
        "should" -> MaterialTheme.colorScheme.surface
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    val accent = when (item.tier) {
        "must" -> MaterialTheme.colorScheme.primary
        "should" -> MaterialTheme.colorScheme.primary.copy(alpha = 0.65f)
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Card(
        onClick = onOpenGoal,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = container),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                item.taskText,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Row {
                Text(
                    "~${item.estMinutes} min",
                    style = MaterialTheme.typography.labelMedium,
                    color = accent,
                )
                if (goal != null) {
                    Spacer(Modifier.size(8.dp))
                    Text(
                        "·  for: ${goal.statement}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            if (item.rationale.isNotBlank()) {
                Text(
                    item.rationale,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Button(
                    onClick = onDone,
                    enabled = !saving,
                    modifier = Modifier.weight(1f),
                ) { Text(if (saving) "…" else "Done") }
                OutlinedButton(
                    onClick = onLater,
                    enabled = !saving,
                    modifier = Modifier.weight(1f),
                ) { Text("Later") }
                OutlinedButton(
                    onClick = onSkip,
                    enabled = !saving,
                    modifier = Modifier.weight(1f),
                ) { Text("Skip") }
                OutlinedButton(
                    onClick = onExplain,
                    enabled = !saving,
                    modifier = Modifier.weight(1.2f),
                ) { Text("Tell Coach") }
            }
        }
    }
}

@Composable
private fun FinishedItemRow(item: DailyPlanItem, goal: Goal?) {
    val label = when (item.state) {
        "done" -> "✓ Done"
        "deferred" -> "Later"
        "declined" -> "Skipped"
        else -> item.state
    }
    Card(
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(10.dp)) {
            Text(
                item.taskText,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textDecoration = if (item.state == "done") TextDecoration.LineThrough else null,
            )
            Row {
                Text(
                    label,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
                if (goal != null) {
                    Text(
                        "  ·  ${goal.statement}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            if (item.deferReason.isNotBlank()) {
                Text(
                    "\"${item.deferReason}\"",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun EmptyPlanCard(
    hasGoals: Boolean,
    onOpenGoals: () -> Unit,
    onOpenChat: () -> Unit,
) {
    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                if (hasGoals) "No items today." else "No goals yet.",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                if (hasGoals)
                    "The Coach didn't propose anything for today. That's okay — capture a thought or talk things through."
                else
                    "Start by saving a goal. Once you have one, the Coach will plan your days against it.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!hasGoals) {
                    Button(onClick = onOpenGoals, modifier = Modifier.weight(1f)) {
                        Text("Goals")
                    }
                }
                OutlinedButton(onClick = onOpenChat, modifier = Modifier.weight(1f)) {
                    Text("Coach")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ExplainSheet(
    item: DailyPlanItem,
    onDismiss: () -> Unit,
    onDefer: (String) -> Unit,
    onSkip: (String) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var reason by remember { mutableStateOf("") }
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
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Tell Coach why", style = MaterialTheme.typography.titleLarge)
            Text(
                item.taskText,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = reason,
                onValueChange = { reason = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Reason") },
                placeholder = { Text("e.g. I'll do that tomorrow while I'm in OKC") },
                minLines = 2,
                maxLines = 5,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) {
                    Text("Cancel")
                }
                Button(
                    onClick = { onDefer(reason.trim()) },
                    enabled = reason.isNotBlank(),
                    modifier = Modifier.weight(1f),
                ) { Text("Defer") }
            }
            TextButton(
                onClick = { onSkip(reason.trim()) },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Skip entirely") }
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
                text = streak.currentStreakLength.toString(),
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
            .background(track, RoundedCornerShape(5.dp)),
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

private fun paceLabel(score: Double?): String = when {
    score == null -> "no data yet"
    score >= 1.5 -> "well above pace"
    score >= 1.0 -> "on pace"
    score > 0.0 -> "below pace"
    else -> "no progress yet"
}

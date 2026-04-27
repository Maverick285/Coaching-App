package com.buddy.app.ui.customize

import android.app.Application
import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.FilterChip
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
import com.buddy.app.data.HealthResponse
import com.buddy.app.data.UsageResponse
import com.buddy.app.interventions.UsageStatsReader
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomizeScreen(
    onBack: () -> Unit,
    viewModel: CustomizeViewModel = viewModel(
        factory = CustomizeViewModel.factory(LocalContext.current.applicationContext as Application)
    ),
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    val context = LocalContext.current
    var showResetConfirm by remember { mutableStateOf(false) }

    LaunchedEffect(state.resetDone) {
        if (state.resetDone) {
            viewModel.onResetHandled()
            // Restart the activity to land back on onboarding cleanly.
            val intent = (context.packageManager.getLaunchIntentForPackage(context.packageName))
                ?.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
            if (intent != null) {
                context.startActivity(intent)
                if (context is android.app.Activity) context.finish()
            }
        }
    }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbar.showSnackbar(it)
            viewModel.onClearError()
        }
    }
    LaunchedEffect(state.message) {
        state.message?.let {
            snackbar.showSnackbar(it)
            viewModel.onClearMessage()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Customize") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back",
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
        if (!state.configured) {
            Text(
                "Configure backend in Settings first.",
                modifier = Modifier.padding(24.dp),
                color = MaterialTheme.colorScheme.onBackground,
            )
            return@Scaffold
        }

        if (state.editingPath != null) {
            FileEditor(
                path = state.editingPath!!,
                content = state.editorContent,
                saving = state.savingFile,
                onChange = viewModel::setEditorContent,
                onSave = viewModel::saveFile,
                onCancel = viewModel::cancelEdit,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
            )
            return@Scaffold
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // --- Status + spend, surfaced at the top -------------------
            StatusCard(
                health = state.health,
                healthError = state.healthError,
                context = context,
            )
            UsageCard(usage = state.usage)

            HorizontalDivider()

            // --- Profile section ---------------------------------------
            SectionHeading("Names")
            OutlinedTextField(
                value = state.userNameInput,
                onValueChange = viewModel::setUserName,
                label = { Text("What the persona calls you") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = state.personaNameInput,
                onValueChange = viewModel::setPersonaName,
                label = { Text("Persona's name") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            HorizontalDivider()

            // --- Model tier --------------------------------------------
            SectionHeading("Model")
            Text(
                "Auto picks the cheap fast model for routine chat and the reasoning model when you ask for planning. Pin it if you want one or the other.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(
                    "auto" to "Auto",
                    "reasoning" to "Reasoning",
                    "fast" to "Fast",
                ).forEach { (id, label) ->
                    FilterChip(
                        selected = state.chatTierInput == id,
                        onClick = { viewModel.setChatTier(id) },
                        label = { Text(label) },
                    )
                }
            }

            Button(
                onClick = viewModel::saveProfile,
                enabled = !state.savingProfile,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (state.savingProfile) {
                    CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.size(6.dp))
                }
                Text("Save")
            }

            HorizontalDivider()

            // --- Memory files ----------------------------------------
            Row(verticalAlignment = Alignment.CenterVertically) {
                SectionHeading("Memory")
                com.buddy.app.ui.common.InfoTooltip(
                    title = "Memory files",
                    body = "PERSONA.md is the persona's behavior spec. MEMORY.md is what it knows about you. PATTERNS.md is the running list of patterns observed. Edit anything; changes apply on the next conversation.",
                )
            }
            CUSTOMIZABLE_MEMORY_FILES.forEach { path ->
                MemoryRow(
                    path = path,
                    bytes = state.files[path]?.length ?: 0,
                    onEdit = { viewModel.openFile(path) },
                )
            }

            HorizontalDivider()

            // --- Quick actions ----------------------------------------
            SectionHeading("Quick actions")
            OutlinedButton(
                onClick = viewModel::resetOnboarding,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Re-run onboarding next launch") }

            Button(
                onClick = { showResetConfirm = true },
                modifier = Modifier.fillMaxWidth(),
                enabled = !state.resetting,
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer,
                    contentColor = MaterialTheme.colorScheme.onErrorContainer,
                ),
            ) {
                if (state.resetting) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.size(6.dp))
                }
                Text("Reset all data")
            }

            OutlinedButton(
                onClick = {
                    val intent = Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    context.startActivity(intent)
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Grant usage-access permission (for drift detection)") }

            OutlinedButton(
                onClick = {
                    val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                        .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    context.startActivity(intent)
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Notification settings") }

            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedButton(
                    onClick = {
                        val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        context.startActivity(intent)
                    },
                    modifier = Modifier.weight(1f),
                ) { Text("Grant accessibility") }
                com.buddy.app.ui.common.InfoTooltip(
                    title = "Accessibility access",
                    body = "Used only for Tier 3 / Tier 4 blocks. Buddy's service reads which app is foregrounded — no screen content, no keystrokes, no text. Skip this unless you've added blocked apps to a goal.",
                )
            }
        }
    }

    if (showResetConfirm) {
        AlertDialog(
            onDismissRequest = { showResetConfirm = false },
            title = { Text("Reset all data?") },
            text = {
                Text(
                    "This wipes every goal, task, conversation, journal entry, persona file, and grade — on the server and on this phone. Your backend connection and Anthropic key stay. There's no undo.",
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    showResetConfirm = false
                    viewModel.factoryReset()
                }) { Text("Yes, wipe everything") }
            },
            dismissButton = {
                TextButton(onClick = { showResetConfirm = false }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun SectionHeading(label: String) {
    Text(
        text = label,
        style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.onBackground,
    )
}

@Composable
private fun MemoryRow(path: String, bytes: Int, onEdit: () -> Unit) {
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = path,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Text(
                    text = if (bytes > 0) "$bytes chars" else "(empty)",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            TextButton(onClick = onEdit) { Text("Edit") }
        }
    }
}

@Composable
private fun FileEditor(
    path: String,
    content: String,
    saving: Boolean,
    onChange: (String) -> Unit,
    onSave: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = path,
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onBackground,
        )
        OutlinedTextField(
            value = content,
            onValueChange = onChange,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            textStyle = MaterialTheme.typography.bodyMedium,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onCancel, modifier = Modifier.weight(1f)) {
                Text("Cancel")
            }
            Button(
                onClick = onSave,
                enabled = !saving,
                modifier = Modifier.weight(1f),
            ) {
                if (saving) {
                    CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.size(6.dp))
                }
                Text("Save")
            }
        }
    }
}

@Composable
private fun StatusCard(
    health: HealthResponse?,
    healthError: String?,
    context: android.content.Context,
) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                "System status",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )

            if (healthError != null) {
                Text(
                    "Backend: unreachable — $healthError",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
                return@Card
            }
            if (health == null) {
                Text(
                    "Backend: checking…",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                return@Card
            }

            val ok = health.status == "ok"
            StatusRow(
                label = "Backend",
                value = "${health.status} · v${health.version}",
                good = ok,
            )
            StatusRow(
                label = "Models",
                value = health.modelsResolved.values.joinToString(),
                good = health.modelsResolved.isNotEmpty() && !health.modelsResolved.containsKey("error"),
            )
            StatusRow(
                label = "Memory repo",
                value = health.memoryRepoStatus,
                good = !health.memoryRepoStatus.startsWith("error"),
            )

            // --- Permissions (phone-side) -----------------------------
            val accessibilityOn = isAccessibilityEnabled(context)
            val usageStatsOn = UsageStatsReader.hasPermission(context)
            val notifsOn = areNotificationsEnabled(context)

            Spacer(Modifier.height(4.dp))
            Text(
                "Permissions",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            StatusRow(label = "Notifications", value = if (notifsOn) "granted" else "missing", good = notifsOn)
            StatusRow(label = "Usage access (phone drift)", value = if (usageStatsOn) "granted" else "missing", good = usageStatsOn)
            StatusRow(label = "Accessibility (T3/T4 blocks)", value = if (accessibilityOn) "granted" else "not granted", good = accessibilityOn)

            // --- Scheduler diagnostics --------------------------------
            health.diagnostics?.let { d ->
                Spacer(Modifier.height(4.dp))
                Text(
                    "Background jobs",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                d.lastConsolidationAt?.let {
                    StatusRow(
                        label = "Last consolidation",
                        value = "${formatIso(it)} · ${d.lastConsolidationStatus.orEmpty()}",
                        good = d.lastConsolidationStatus?.startsWith("ok") == true,
                    )
                } ?: StatusRow(label = "Last consolidation", value = "never run", good = null)

                d.lastBackupPushAt?.let {
                    StatusRow(
                        label = "Last backup push",
                        value = "${formatIso(it)} · ${d.lastBackupPushStatus.orEmpty()}",
                        good = d.lastBackupPushStatus == "pushed",
                    )
                } ?: StatusRow(
                    label = "Backup push",
                    value = if (d.gitRemoteConfigured) "never run" else "no remote configured",
                    good = null,
                )

                d.lastEngineTickAt?.let {
                    StatusRow(
                        label = "Drift engine tick",
                        value = "${formatIso(it)} · fired ${d.lastEngineTickFired.orEmpty()}",
                        good = true,
                    )
                }

                if (d.scheduledJobs.isNotEmpty()) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Next runs",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    d.scheduledJobs.forEach { job ->
                        StatusRow(
                            label = job.id,
                            value = job.nextRunAt?.let(::formatIso) ?: "(unscheduled)",
                            good = null,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun UsageCard(usage: UsageResponse?) {
    if (usage == null) return
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                "API spend",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )

            val mtd = usage.monthToDate.costUsd
            val soft = usage.softCapUsd.coerceAtLeast(0.01)
            val ratio = (mtd / soft).coerceIn(0.0, 2.0).toFloat()

            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "$%.2f".format(mtd),
                    style = MaterialTheme.typography.displaySmall,
                    color = if (usage.hardCapExceeded) MaterialTheme.colorScheme.error
                        else if (usage.softCapExceeded) MaterialTheme.colorScheme.error
                        else MaterialTheme.colorScheme.onSurface,
                )
                Spacer(Modifier.size(8.dp))
                Text(
                    text = "month-to-date",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            LinearProgressIndicator(
                progress = { ratio.coerceAtMost(1f) },
                modifier = Modifier.fillMaxWidth(),
                trackColor = MaterialTheme.colorScheme.surfaceVariant,
            )
            Text(
                text = "Soft cap $%.0f · Hard cap $%.0f".format(usage.softCapUsd, usage.hardCapUsd),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (usage.hardCapExceeded) {
                Text(
                    "Hard cap reached — /converse returns 503 until next month or you raise BUDDY_BUDGET_HARD_USD.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            } else if (usage.softCapExceeded) {
                Text(
                    "Soft cap exceeded. Operations continue; consider tightening if this surprises you.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    "Today $%.2f".format(usage.today.costUsd),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "7-day $%.2f".format(usage.last7Days.costUsd),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun StatusRow(label: String, value: String, good: Boolean?) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f),
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            color = when (good) {
                true -> MaterialTheme.colorScheme.onSurface
                false -> MaterialTheme.colorScheme.error
                null -> MaterialTheme.colorScheme.onSurfaceVariant
            },
        )
    }
}

private fun isAccessibilityEnabled(context: android.content.Context): Boolean {
    return try {
        val expected = "${context.packageName}/com.buddy.app.blocking.BuddyAccessibilityService"
        val enabled = android.provider.Settings.Secure.getString(
            context.contentResolver,
            android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
        ) ?: ""
        enabled.split(":").any { it.equals(expected, ignoreCase = true) }
    } catch (_: Exception) {
        false
    }
}

private fun areNotificationsEnabled(context: android.content.Context): Boolean =
    androidx.core.app.NotificationManagerCompat.from(context).areNotificationsEnabled()

private fun formatIso(iso: String): String = try {
    // Server returns naive UTC ISO. Render as 'MMM d, HH:mm' in local TZ
    // for the most-recent occurrence the user cares about.
    val instant = if (iso.endsWith("Z") || iso.contains("+")) {
        java.time.OffsetDateTime.parse(iso).toInstant()
    } else {
        java.time.LocalDateTime.parse(iso).toInstant(java.time.ZoneOffset.UTC)
    }
    java.time.ZonedDateTime.ofInstant(instant, java.time.ZoneId.systemDefault())
        .format(java.time.format.DateTimeFormatter.ofPattern("MMM d, HH:mm"))
} catch (_: Exception) {
    iso
}

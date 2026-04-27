package com.buddy.app.ui.tasks

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.buddy.app.data.Task
import com.buddy.app.voice.SpeechRecognition
import com.buddy.app.voice.VoiceEvent
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TasksScreen(
    viewModel: TasksViewModel = viewModel(
        factory = TasksViewModel.factory(
            LocalContext.current.applicationContext as Application
        )
    ),
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val speech = remember(context) { SpeechRecognition(context) }
    val voiceJobHolder = remember { mutableStateOf<Job?>(null) }
    var editingTask by remember { mutableStateOf<Task?>(null) }
    var deleteConfirmId by remember { mutableStateOf<Int?>(null) }

    fun cancelVoice() {
        voiceJobHolder.value?.cancel()
        voiceJobHolder.value = null
    }

    fun startVoice() {
        if (!speech.isAvailable()) {
            return
        }
        voiceJobHolder.value = scope.launch {
            speech.listen().collectLatest { ev ->
                when (ev) {
                    is VoiceEvent.Partial -> viewModel.setNlText(ev.text)
                    is VoiceEvent.Final -> {
                        viewModel.setNlText(ev.text)
                        viewModel.runNlBatch(source = "voice")
                    }
                    else -> Unit
                }
            }
        }
    }

    val micPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> if (granted) startVoice() }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbar.showSnackbar(it)
            viewModel.onClearError()
        }
    }
    LaunchedEffect(state.info) {
        state.info?.let {
            snackbar.showSnackbar(it)
            viewModel.onClearInfo()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Tasks") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    titleContentColor = MaterialTheme.colorScheme.onBackground,
                ),
            )
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
                return@Scaffold
            }

            val grouped = state.tasks
                .filter { it.state != "done" }
                .groupBy { it.goalId }
            val done = state.tasks.filter { it.state == "done" }

            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (grouped.isEmpty() && done.isEmpty()) {
                    item {
                        EmptyHelp()
                    }
                }
                grouped.forEach { (goalId, tasks) ->
                    val goal = state.goalsById[goalId]
                    item {
                        Text(
                            text = goal?.statement ?: "Goal #$goalId",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.padding(top = 8.dp, bottom = 4.dp),
                        )
                    }
                    items(tasks, key = { "open-${it.id}" }) { t ->
                        TaskRow(
                            task = t,
                            onToggle = { viewModel.toggleDone(t) },
                            onEdit = { editingTask = t },
                            onDelete = { deleteConfirmId = t.id },
                        )
                    }
                }
                if (done.isNotEmpty()) {
                    item {
                        Text(
                            text = "Done",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 16.dp, bottom = 4.dp),
                        )
                    }
                    items(done.take(20), key = { "done-${it.id}" }) { t ->
                        TaskRow(
                            task = t,
                            onToggle = { viewModel.toggleDone(t) },
                            onEdit = { editingTask = t },
                            onDelete = { deleteConfirmId = t.id },
                        )
                    }
                }
            }

            NlComposer(
                text = state.nlText,
                running = state.nlRunning,
                onTextChanged = viewModel::setNlText,
                onSend = { viewModel.runNlBatch(source = "text") },
                onMicPress = {
                    if (ContextCompat.checkSelfPermission(
                            context, Manifest.permission.RECORD_AUDIO
                        ) == PackageManager.PERMISSION_GRANTED
                    ) startVoice()
                    else micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                },
                onMicRelease = ::cancelVoice,
            )
        }
    }

    editingTask?.let { t ->
        EditTaskDialog(
            task = t,
            onDismiss = { editingTask = null },
            onSave = { description, minutes ->
                viewModel.editTask(t.id, description, minutes)
                editingTask = null
            },
        )
    }
    deleteConfirmId?.let { id ->
        AlertDialog(
            onDismissRequest = { deleteConfirmId = null },
            title = { Text("Delete this task?") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.deleteTask(id)
                    deleteConfirmId = null
                }) { Text("Delete") }
            },
            dismissButton = {
                TextButton(onClick = { deleteConfirmId = null }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun TaskRow(
    task: Task,
    onToggle: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    var menuOpen by remember { mutableStateOf(false) }
    Card(
        onClick = onEdit,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = task.state == "done", onCheckedChange = { onToggle() })
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = task.description,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    textDecoration = if (task.state == "done") TextDecoration.LineThrough else null,
                )
                val sub = buildList {
                    task.estimatedDurationMinutes?.let { add("${it}m") }
                    task.scheduledAt?.takeIf { it.isNotEmpty() }?.let { add(prettyTime(it)) }
                }.joinToString(" · ")
                if (sub.isNotEmpty()) {
                    Text(
                        text = sub,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Box {
                TextButton(onClick = { menuOpen = true }) { Text("⋯") }
                DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                    DropdownMenuItem(
                        text = { Text("Edit") },
                        onClick = { menuOpen = false; onEdit() },
                    )
                    DropdownMenuItem(
                        text = { Text("Delete") },
                        onClick = { menuOpen = false; onDelete() },
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EditTaskDialog(
    task: Task,
    onDismiss: () -> Unit,
    onSave: (description: String, minutes: Int?) -> Unit,
) {
    var description by remember { mutableStateOf(task.description) }
    var minutesText by remember {
        mutableStateOf(task.estimatedDurationMinutes?.toString().orEmpty())
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Edit task") },
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
                    label = { Text("Estimated minutes") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                if (description.isNotBlank()) {
                    onSave(description.trim(), minutesText.toIntOrNull())
                }
            }) { Text("Save") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}

@Composable
private fun NlComposer(
    text: String,
    running: Boolean,
    onTextChanged: (String) -> Unit,
    onSend: () -> Unit,
    onMicPress: () -> Unit,
    onMicRelease: () -> Unit,
) {
    Surface(color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .imePadding()
                .navigationBarsPadding()
                .padding(horizontal = 8.dp, vertical = 8.dp),
        ) {
            Text(
                text = "Tell me what to do — \"add task: write 200 words at 9am, mark dishes done, scrap the gym one\"",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
            )
            Row(verticalAlignment = Alignment.Bottom) {
                OutlinedTextField(
                    value = text,
                    onValueChange = onTextChanged,
                    placeholder = { Text("Add / edit / end tasks…") },
                    modifier = Modifier.weight(1f).widthIn(min = 0.dp),
                    maxLines = 4,
                    enabled = !running,
                )
                Spacer(Modifier.size(6.dp))
                MicButton(
                    onPress = onMicPress,
                    onRelease = onMicRelease,
                    enabled = !running,
                )
                Spacer(Modifier.size(6.dp))
                FloatingActionButton(
                    onClick = onSend,
                    modifier = Modifier.size(48.dp),
                    containerColor = MaterialTheme.colorScheme.primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary,
                ) {
                    if (running) {
                        CircularProgressIndicator(
                            strokeWidth = 2.dp,
                            modifier = Modifier.size(20.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                    } else {
                        Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
                    }
                }
            }
        }
    }
}

@Composable
private fun MicButton(onPress: () -> Unit, onRelease: () -> Unit, enabled: Boolean) {
    var pressed by remember { mutableStateOf(false) }
    Box(
        modifier = Modifier
            .size(48.dp)
            .background(
                color = if (pressed) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.surfaceVariant,
                shape = CircleShape,
            )
            .pointerInput(enabled) {
                if (!enabled) return@pointerInput
                awaitEachGesture {
                    awaitFirstDown(requireUnconsumed = false)
                    pressed = true
                    onPress()
                    try {
                        waitForUpOrCancellation()
                    } finally {
                        pressed = false
                        onRelease()
                    }
                }
            },
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            Icons.Filled.Mic,
            contentDescription = "Voice",
            tint = if (pressed) MaterialTheme.colorScheme.onPrimary
            else MaterialTheme.colorScheme.onSurface,
        )
    }
}

@Composable
private fun EmptyHelp() {
    Card(
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                "No open tasks.",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                "Type or speak below. Examples:\n" +
                        "• \"add task: outline the talk for 30m, write intro tomorrow at 9am\"\n" +
                        "• \"mark dishes done, end the gym one\"\n" +
                        "• \"reschedule the spec to Friday\"",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private fun prettyTime(iso: String): String = try {
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

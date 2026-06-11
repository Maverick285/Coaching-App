package com.buddy.app.capture

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.buddy.app.data.CaptureAction
import com.buddy.app.ui.theme.BuddyTheme
import com.buddy.app.voice.SpeechRecognition
import com.buddy.app.voice.VoiceEvent
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * Capture-anywhere entry point. Started by:
 *   - the in-app composer's "+" / mic button (Phase 1 path stays available)
 *   - the home-screen widget tap (Phase 3 path, sets EXTRA_SOURCE = "widget")
 */
class CaptureActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val source = intent.getStringExtra(EXTRA_SOURCE) ?: "manual"
        setContent {
            BuddyTheme {
                CaptureRoot(source = source, onClose = { finish() })
            }
        }
    }

    companion object {
        const val EXTRA_SOURCE = "source"
    }
}

@Composable
private fun CaptureRoot(source: String, onClose: () -> Unit) {
    val viewModel: CaptureViewModel = viewModel(
        factory = CaptureViewModel.factory(
            LocalContext.current.applicationContext as Application
        )
    )
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    val speech = remember(context) { SpeechRecognition(context) }
    val scope = rememberCoroutineScope()
    val voiceJobHolder = remember { mutableStateOf<Job?>(null) }

    LaunchedEffect(Unit) { viewModel.setSource(source) }

    fun beginListening() {
        if (!speech.isAvailable()) {
            viewModel.onVoiceError("Voice recognition isn't available on this device.")
            return
        }
        voiceJobHolder.value?.cancel()
        voiceJobHolder.value = scope.launch {
            speech.listen().collectLatest { ev ->
                when (ev) {
                    is VoiceEvent.Partial -> viewModel.onPartial(ev.text)
                    is VoiceEvent.Final -> viewModel.onFinal(ev.text)
                    is VoiceEvent.Error -> viewModel.onVoiceError(ev.message)
                    else -> Unit
                }
            }
        }
    }

    val micPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) beginListening()
        else viewModel.onVoiceError("Microphone permission required.")
    }

    LaunchedEffect(state.stage) {
        if (state.stage == CaptureStage.LISTENING) {
            val granted = ContextCompat.checkSelfPermission(
                context, Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED
            if (granted) beginListening()
            else micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp),
            contentAlignment = Alignment.Center,
        ) {
            Card(
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
                modifier = Modifier
                    .widthIn(max = 480.dp)
                    .fillMaxWidth(),
            ) {
                Column(modifier = Modifier.padding(24.dp)) {
                    when (state.stage) {
                        CaptureStage.LISTENING -> ListeningPanel(state)
                        CaptureStage.DISPATCHING ->
                            DispatchingPanel(state.finalTranscript)
                        CaptureStage.CONFIRMING ->
                            ConfirmingPanel(
                                state = state,
                                onConfirm = viewModel::confirm,
                                onCancel = onClose,
                            )
                        CaptureStage.DONE -> DonePanel(state, onClose)
                        CaptureStage.ERROR -> ErrorPanel(
                            message = state.error.orEmpty(),
                            onRetry = viewModel::reset,
                            onClose = onClose,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ListeningPanel(state: CaptureUiState) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            Icons.Filled.Mic,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.size(10.dp))
        Text(
            text = "Listening",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
    Spacer(Modifier.height(12.dp))
    Text(
        text = state.partialTranscript.ifEmpty { "Speak naturally. Tap the field to type instead." },
        style = MaterialTheme.typography.bodyLarge,
        color = if (state.partialTranscript.isEmpty()) {
            MaterialTheme.colorScheme.onSurfaceVariant
        } else MaterialTheme.colorScheme.onSurface,
    )
}

@Composable
private fun DispatchingPanel(transcript: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        CircularProgressIndicator(
            strokeWidth = 2.dp,
            modifier = Modifier.size(18.dp),
        )
        Spacer(Modifier.size(10.dp))
        Text(
            text = "Working",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
    Spacer(Modifier.height(12.dp))
    Text(
        text = transcript,
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
}

@Composable
private fun ConfirmingPanel(
    state: CaptureUiState,
    onConfirm: (List<CaptureAction>) -> Unit,
    onCancel: () -> Unit,
) {
    val classification = state.classification ?: return
    val initiallySelected: Set<Int> = remember(classification) {
        classification.actions.indices.toSet()
    }
    var selected by remember(classification) { mutableStateOf<Set<Int>>(initiallySelected) }

    Text(
        text = "Confirm",
        style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Spacer(Modifier.height(4.dp))
    Text(
        text = state.finalTranscript,
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(14.dp))

    if (classification.actions.isEmpty()) {
        Text(
            text = classification.fallbackMessage.ifEmpty { "Nothing actionable found." },
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
    } else {
        classification.actions.forEachIndexed { idx, action ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Checkbox(
                    checked = idx in selected,
                    onCheckedChange = {
                        selected = if (idx in selected) selected - idx else selected + idx
                    },
                )
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = action.summary,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Text(
                        text = "${action.kind} · conf ${"%.2f".format(action.confidence)}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }

    Spacer(Modifier.height(16.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(onClick = onCancel, modifier = Modifier.weight(1f)) {
            Text("Cancel")
        }
        Button(
            onClick = {
                val chosen = classification.actions
                    .filterIndexed { i, _ -> i in selected }
                onConfirm(chosen)
            },
            modifier = Modifier.weight(1f),
            enabled = classification.actions.isNotEmpty(),
        ) {
            Text("Confirm")
        }
    }
}

@Composable
private fun DonePanel(state: CaptureUiState, onClose: () -> Unit) {
    Text(
        text = "Captured",
        style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Spacer(Modifier.height(8.dp))
    state.dispatch?.results?.forEach { res ->
        val mark = if (res.success) "✓" else "—"
        Text(
            text = "$mark  ${res.detail.ifEmpty { res.kind }}",
            style = MaterialTheme.typography.bodyMedium,
            color = if (res.success) {
                MaterialTheme.colorScheme.onSurface
            } else MaterialTheme.colorScheme.error,
        )
    } ?: Text(
        text = "Nothing dispatched.",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(16.dp))
    Button(onClick = onClose, modifier = Modifier.fillMaxWidth()) {
        Text("Done")
    }
}

@Composable
private fun ErrorPanel(
    message: String,
    onRetry: () -> Unit,
    onClose: () -> Unit,
) {
    Text(
        text = "Couldn't capture",
        style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Spacer(Modifier.height(8.dp))
    Text(
        text = message.ifEmpty { "Unknown error." },
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.error,
    )
    Spacer(Modifier.height(16.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(onClick = onClose, modifier = Modifier.weight(1f)) { Text("Close") }
        Button(onClick = onRetry, modifier = Modifier.weight(1f)) { Text("Try again") }
    }
}

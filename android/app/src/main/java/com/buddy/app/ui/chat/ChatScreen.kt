package com.buddy.app.ui.chat

import android.Manifest
import android.app.Application
import android.content.pm.PackageManager
import android.content.Intent
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
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.buddy.app.R
import com.buddy.app.capture.CaptureActivity
import com.buddy.app.ui.theme.AssistantBubble
import com.buddy.app.ui.theme.UserBubble
import com.buddy.app.voice.SpeechRecognition
import com.buddy.app.voice.VoiceEvent
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    onOpenSettings: () -> Unit,
    viewModel: ChatViewModel = viewModel(
        factory = ChatViewModel.factory(
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

    fun cancelVoice() {
        voiceJobHolder.value?.cancel()
        voiceJobHolder.value = null
    }

    fun startVoice() {
        if (!speech.isAvailable()) {
            viewModel.onVoiceCancelled(context.getString(R.string.msg_voice_unavailable))
            return
        }
        viewModel.onVoiceStarted()
        voiceJobHolder.value = scope.launch {
            speech.listen().collectLatest { ev -> handleVoiceEvent(ev, viewModel) }
        }
    }

    val micPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            startVoice()
        } else {
            viewModel.onVoiceCancelled(context.getString(R.string.msg_record_audio_required))
        }
    }

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
                title = { Text(stringResource(R.string.title_chat)) },
                actions = {
                    IconButton(onClick = {
                        val intent = Intent(context, CaptureActivity::class.java).apply {
                            putExtra(CaptureActivity.EXTRA_SOURCE, "chat_topbar")
                        }
                        context.startActivity(intent)
                    }) {
                        Icon(
                            Icons.Filled.GraphicEq,
                            contentDescription = "Capture",
                        )
                    }
                    IconButton(onClick = { viewModel.startNewSession() }) {
                        Icon(
                            Icons.Filled.Add,
                            contentDescription = stringResource(R.string.action_new_session),
                        )
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(
                            Icons.Filled.Settings,
                            contentDescription = stringResource(R.string.action_settings),
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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (!state.backendConfigured) {
                EmptyConfigPanel(onOpenSettings)
            } else {
                if (state.messages.isEmpty() && !state.isSending) {
                    androidx.compose.foundation.layout.Box(
                        modifier = Modifier.weight(1f).fillMaxWidth(),
                        contentAlignment = Alignment.Center,
                    ) {
                        com.buddy.app.ui.quotes.WelcomeQuote()
                    }
                } else {
                    MessagesList(
                        messages = state.messages,
                        isSending = state.isSending,
                        onConfirmProposal = { id, payload ->
                            viewModel.confirmProposeGoal(id, payload)
                        },
                        onDismissProposal = { id -> viewModel.dismissProposal(id) },
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth(),
                    )
                }
                if (state.isListening) {
                    ListeningBar(state.partialTranscript)
                }
                Composer(
                    text = state.composerText,
                    onTextChanged = viewModel::onComposerChanged,
                    onSend = { viewModel.send() },
                    sending = state.isSending,
                    onMicPress = {
                        if (ContextCompat.checkSelfPermission(
                                context, Manifest.permission.RECORD_AUDIO
                            ) == PackageManager.PERMISSION_GRANTED
                        ) {
                            startVoice()
                        } else {
                            micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    },
                    onMicRelease = { cancelVoice() },
                )
            }
        }
    }
}

private fun handleVoiceEvent(ev: VoiceEvent, viewModel: ChatViewModel) {
    when (ev) {
        is VoiceEvent.Partial -> viewModel.onVoicePartial(ev.text)
        is VoiceEvent.Final -> viewModel.onVoiceFinal(ev.text)
        is VoiceEvent.Error -> viewModel.onVoiceCancelled(ev.message)
        VoiceEvent.EndOfSpeech,
        VoiceEvent.BeginningOfSpeech,
        VoiceEvent.ReadyForSpeech,
        -> Unit
    }
}

@Composable
private fun EmptyConfigPanel(onOpenSettings: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = stringResource(R.string.msg_settings_required),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onBackground,
        )
        Spacer(Modifier.height(16.dp))
        FloatingActionButton(onClick = onOpenSettings) {
            Icon(Icons.Filled.Settings, contentDescription = null)
        }
    }
}

@Composable
private fun MessagesList(
    messages: List<ChatMessage>,
    isSending: Boolean,
    onConfirmProposal: (messageId: String, payload: kotlinx.serialization.json.JsonObject) -> Unit = { _, _ -> },
    onDismissProposal: (messageId: String) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val listState = rememberLazyListState()

    LaunchedEffect(messages.size, isSending) {
        if (messages.isNotEmpty()) {
            val target = messages.lastIndex + if (isSending) 1 else 0
            listState.animateScrollToItem(target.coerceAtLeast(0))
        }
    }

    LazyColumn(
        state = listState,
        modifier = modifier.padding(horizontal = 12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(vertical = 12.dp),
    ) {
        items(messages, key = { it.id }) { msg ->
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                MessageBubble(msg)
                msg.proposals.forEach { proposal ->
                    if (proposal.kind == "propose_goal") {
                        ProposeGoalCard(
                            payload = proposal.payload,
                            onConfirm = { onConfirmProposal(msg.id, proposal.payload) },
                            onDismiss = { onDismissProposal(msg.id) },
                        )
                    }
                }
            }
        }
        if (isSending) {
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Start,
                ) {
                    Surface(
                        color = AssistantBubble,
                        shape = RoundedCornerShape(16.dp),
                    ) {
                        Box(modifier = Modifier.padding(12.dp)) {
                            CircularProgressIndicator(
                                strokeWidth = 2.dp,
                                modifier = Modifier.size(16.dp),
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MessageBubble(msg: ChatMessage) {
    val isUser = msg.role == ChatRole.USER
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        Surface(
            color = if (isUser) UserBubble else AssistantBubble,
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                Text(
                    text = msg.content,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                if (!isUser && msg.modelUsed.isNotEmpty()) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        text = msg.modelUsed,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun ListeningBar(partial: String) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        shape = RoundedCornerShape(12.dp),
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.Filled.Mic,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.size(8.dp))
            Text(
                text = partial.ifBlank { stringResource(R.string.msg_listening) },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
    }
}

@Composable
private fun Composer(
    text: String,
    onTextChanged: (String) -> Unit,
    onSend: () -> Unit,
    sending: Boolean,
    onMicPress: () -> Unit,
    onMicRelease: () -> Unit,
) {
    Surface(color = MaterialTheme.colorScheme.background) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .imePadding()
                .navigationBarsPadding()
                .padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            OutlinedTextField(
                value = text,
                onValueChange = onTextChanged,
                placeholder = { Text(stringResource(R.string.hint_message)) },
                modifier = Modifier.weight(1f),
                maxLines = 6,
                enabled = !sending,
            )
            Spacer(Modifier.size(6.dp))
            MicButton(onPress = onMicPress, onRelease = onMicRelease, enabled = !sending)
            Spacer(Modifier.size(6.dp))
            FloatingActionButton(
                onClick = onSend,
                modifier = Modifier.size(48.dp),
                containerColor = MaterialTheme.colorScheme.primary,
                contentColor = MaterialTheme.colorScheme.onPrimary,
            ) {
                Icon(
                    Icons.AutoMirrored.Filled.Send,
                    contentDescription = stringResource(R.string.action_send),
                )
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
                color = if (pressed) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.surfaceVariant
                },
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
            contentDescription = stringResource(R.string.action_voice),
            tint = if (pressed) {
                MaterialTheme.colorScheme.onPrimary
            } else {
                MaterialTheme.colorScheme.onSurface
            },
        )
    }
}

/**
 * Inline confirmation card for a `propose_goal` tool call. The
 * persona's prose still appears in the bubble above; this is the
 * one-tap save affordance the user confirms or dismisses.
 *
 * Renders the proposed statement, priority, deadline (if any), and
 * pace target (if any) so the user can audit before saving. Edits
 * happen on the goal-detail screen post-save — keeping the card
 * one-tap is the point.
 */
@Composable
private fun ProposeGoalCard(
    payload: kotlinx.serialization.json.JsonObject,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    fun str(key: String): String = payload[key]
        ?.toString()?.trim('"')?.takeIf { it != "null" && it.isNotEmpty() }
        .orEmpty()

    val statement = str("statement")
    val priority = str("priority").toIntOrNull() ?: 3
    val deadline = str("deadline")
    val paceAmt = str("pace_target_amount")
    val paceUnit = str("pace_target_unit")
    val mvp = str("mvp_threshold")
    val priorityLabel = when (priority) {
        1 -> "low"; 2 -> "low-mid"; 4 -> "high"; 5 -> "top"; else -> "medium"
    }

    androidx.compose.material3.Card(
        shape = androidx.compose.foundation.shape.RoundedCornerShape(14.dp),
        colors = androidx.compose.material3.CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                "Proposed goal",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold,
            )
            Text(
                statement.ifBlank { "(missing statement)" },
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )
            val meta = buildList {
                add("Priority: $priorityLabel")
                if (deadline.isNotEmpty()) add("Deadline: $deadline")
                if (paceAmt.isNotEmpty() && paceUnit.isNotEmpty()) add("Pace: $paceAmt $paceUnit/day")
                if (mvp.isNotEmpty()) add("Floor: $mvp")
            }.joinToString("  ·  ")
            if (meta.isNotEmpty()) {
                Text(
                    meta,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                androidx.compose.material3.Button(
                    onClick = onConfirm,
                    modifier = Modifier.weight(1f),
                    enabled = statement.isNotBlank(),
                ) { Text("Save goal") }
                androidx.compose.material3.OutlinedButton(
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                ) { Text("Dismiss") }
            }
        }
    }
}

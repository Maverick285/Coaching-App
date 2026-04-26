package com.buddy.app.blocking

import android.app.Application
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.buddy.app.ui.theme.BuddyTheme

/**
 * Tier 3 — friction with a 60-second countdown + reason field.
 * Tier 4 — hard block: no countdown, only the override pathway.
 *
 * The override flow is in-flow: tap "Request override" → backend texts
 * the approver → user enters the 6-digit code → backend redeems → window
 * opens for `active_minutes` and BlockState locally suppresses.
 */
class FrictionOverlayActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pkg = intent.getStringExtra(EXTRA_PACKAGE).orEmpty()
        val goalId = intent.getIntExtra(EXTRA_GOAL_ID, 0)
        val sessionId = intent.getIntExtra(EXTRA_SESSION_ID, 0)
        val tier = intent.getIntExtra(EXTRA_BLOCK_TIER, 3)

        setContent {
            BuddyTheme {
                FrictionOverlayRoot(
                    pkg = pkg,
                    goalId = goalId,
                    sessionId = sessionId,
                    tier = tier,
                    onClose = { finish() },
                )
            }
        }
    }

    companion object {
        const val EXTRA_PACKAGE = "package"
        const val EXTRA_GOAL_ID = "goal_id"
        const val EXTRA_SESSION_ID = "session_id"
        const val EXTRA_BLOCK_TIER = "block_tier"
    }
}

@Composable
private fun FrictionOverlayRoot(
    pkg: String,
    goalId: Int,
    sessionId: Int,
    tier: Int,
    onClose: () -> Unit,
) {
    val viewModel: FrictionOverlayViewModel = viewModel(
        factory = FrictionOverlayViewModel.factory(
            LocalContext.current.applicationContext as Application
        )
    )
    val state by viewModel.state.collectAsState()

    LaunchedEffect(pkg, tier) {
        viewModel.init(pkg, goalId, sessionId, tier)
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
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 480.dp),
            ) {
                Column(modifier = Modifier.padding(24.dp)) {
                    Header(packageName = state.packageName, blockTier = state.blockTier)
                    Spacer(Modifier.height(14.dp))

                    when (state.phase) {
                        FrictionPhase.WAITING -> WaitingPanel(state, viewModel)
                        FrictionPhase.READY_TO_PROCEED ->
                            ReadyPanel(onProceed = onClose, onOverride = viewModel::openOverrideRequest)
                        FrictionPhase.PROMPT_OVERRIDE ->
                            PromptOverridePanel(state, viewModel, onClose = onClose)
                        FrictionPhase.REQUESTING -> WaitingForRequest()
                        FrictionPhase.AWAITING_CODE -> CodeEntryPanel(state, viewModel)
                        FrictionPhase.REDEEMING -> WaitingForRequest()
                        FrictionPhase.OVERRIDDEN -> OverriddenPanel(state, onClose = onClose)
                        FrictionPhase.ERROR -> ErrorPanel(state.error.orEmpty(), viewModel::reset, onClose)
                    }
                }
            }
        }
    }
}

@Composable
private fun Header(packageName: String, blockTier: Int) {
    Text(
        text = if (blockTier == 4) "Blocked" else "Slow down",
        style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Spacer(Modifier.height(4.dp))
    Text(
        text = packageName.ifEmpty { "(unknown app)" },
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun WaitingPanel(state: FrictionUiState, vm: FrictionOverlayViewModel) {
    Text(
        text = "Sixty-second pause. The session you set is more important than this app right now. If it really is the right call, type why and proceed.",
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Spacer(Modifier.height(12.dp))
    LinearProgressIndicator(
        progress = { 1f - (state.secondsRemaining / 60f) },
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(Modifier.height(6.dp))
    Text(
        "${state.secondsRemaining}s",
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(14.dp))
    OutlinedTextField(
        value = state.reason,
        onValueChange = vm::setReason,
        label = { Text("Reason (optional, logged)") },
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun ReadyPanel(onProceed: () -> Unit, onOverride: () -> Unit) {
    Text(
        "Pause done. You can proceed, or escalate to an override request if a stricter block is in your way later.",
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Spacer(Modifier.height(16.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(onClick = onOverride, modifier = Modifier.weight(1f)) {
            Text("Request override")
        }
        Button(onClick = onProceed, modifier = Modifier.weight(1f)) {
            Text("Proceed")
        }
    }
}

@Composable
private fun PromptOverridePanel(
    state: FrictionUiState,
    vm: FrictionOverlayViewModel,
    onClose: () -> Unit,
) {
    Text(
        "This app is hard-blocked for the rest of the session. To bypass, request an override — your approver gets a one-time code by SMS, you enter the code here, and you get fifteen minutes of grace.",
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Spacer(Modifier.height(12.dp))
    OutlinedTextField(
        value = state.reason,
        onValueChange = vm::setReason,
        label = { Text("Reason (sent to approver)") },
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(Modifier.height(14.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(onClick = onClose, modifier = Modifier.weight(1f)) {
            Text("Close")
        }
        Button(
            onClick = { vm.openOverrideRequest() },
            enabled = state.reason.isNotBlank(),
            modifier = Modifier.weight(1f),
        ) {
            Text("Request override")
        }
    }
}

@Composable
private fun WaitingForRequest() {
    Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator()
    }
}

@Composable
private fun CodeEntryPanel(state: FrictionUiState, vm: FrictionOverlayViewModel) {
    Text(
        text = state.message ?: "Enter the 6-digit code your approver received by SMS.",
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Spacer(Modifier.height(12.dp))
    OutlinedTextField(
        value = state.codeInput,
        onValueChange = vm::setCode,
        label = { Text("Code") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    state.error?.let {
        Spacer(Modifier.height(6.dp))
        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
    }
    Spacer(Modifier.height(14.dp))
    Button(
        onClick = vm::redeemCode,
        enabled = state.codeInput.length == 6,
        modifier = Modifier.fillMaxWidth(),
    ) { Text("Redeem") }
}

@Composable
private fun OverriddenPanel(state: FrictionUiState, onClose: () -> Unit) {
    Text(
        text = state.message ?: "Override active.",
        style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.onSurface,
    )
    Spacer(Modifier.height(16.dp))
    Button(onClick = onClose, modifier = Modifier.fillMaxWidth()) { Text("Done") }
}

@Composable
private fun ErrorPanel(message: String, onRetry: () -> Unit, onClose: () -> Unit) {
    Text(
        text = "Override failed: $message",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.error,
    )
    Spacer(Modifier.height(12.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(onClick = onClose, modifier = Modifier.weight(1f)) { Text("Close") }
        Button(onClick = onRetry, modifier = Modifier.weight(1f)) { Text("Retry") }
    }
}

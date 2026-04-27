package com.buddy.app.ui.onboarding

import android.Manifest
import android.app.Application
import android.app.TimePickerDialog
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingScreen(
    onComplete: () -> Unit,
    viewModel: OnboardingViewModel = viewModel(
        factory = OnboardingViewModel.factory(
            LocalContext.current.applicationContext as Application
        )
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
        snackbarHost = { SnackbarHost(snackbar) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        Surface(
            color = MaterialTheme.colorScheme.background,
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            Box(modifier = Modifier.fillMaxSize().padding(20.dp)) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .widthIn(max = 540.dp)
                        .align(Alignment.Center),
                ) {
                    StepProgress(state.step)
                    Spacer(Modifier.height(20.dp))

                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .verticalScroll(rememberScrollState())
                            .weight(1f),
                    ) {
                        when (state.step) {
                            OnboardingStep.WELCOME -> WelcomeStep(viewModel::next)
                            OnboardingStep.BACKEND -> BackendStep(state, viewModel)
                            OnboardingStep.INTAKE -> IntakeStep(state, viewModel)
                            OnboardingStep.RHYTHM -> RhythmStep(state, viewModel)
                            OnboardingStep.FIRST_GOAL -> FirstGoalStep(state, viewModel)
                            OnboardingStep.DONE -> DoneStep { viewModel.finish(onComplete) }
                        }
                    }

                    if (state.step != OnboardingStep.WELCOME && state.step != OnboardingStep.DONE) {
                        Spacer(Modifier.height(8.dp))
                        TextButton(onClick = { viewModel.back() }) {
                            Text("← Back")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StepProgress(step: OnboardingStep) {
    val total = OnboardingStep.values().size - 1  // exclude DONE from progress count
    val index = step.ordinal.coerceAtMost(total)
    LinearProgressIndicator(
        progress = { index.toFloat() / total.toFloat() },
        modifier = Modifier.fillMaxWidth(),
        trackColor = MaterialTheme.colorScheme.surfaceVariant,
    )
}

@Composable
private fun StepHeading(title: String, subtitle: String? = null) {
    Text(
        text = title,
        style = MaterialTheme.typography.displaySmall,
        color = MaterialTheme.colorScheme.onBackground,
    )
    if (subtitle != null) {
        Spacer(Modifier.height(8.dp))
        Text(
            text = subtitle,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun WelcomeStep(onNext: () -> Unit) {
    StepHeading(
        title = "Welcome.",
        subtitle = "Let's set this up — backend connection, persona calibration, your daily rhythm. About five minutes; you can skip any step and come back from Settings.",
    )
    Spacer(Modifier.height(28.dp))
    Button(onClick = onNext, modifier = Modifier.fillMaxWidth()) { Text("Begin") }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BackendStep(state: OnboardingUiState, vm: OnboardingViewModel) {
    StepHeading(
        title = "Backend",
        subtitle = "Where the persona's memory lives. URL + bearer token from your .env. Test connection before moving on.",
    )
    Spacer(Modifier.height(20.dp))

    OutlinedTextField(
        value = state.backendUrl,
        onValueChange = vm::setBackendUrl,
        label = { Text("Backend URL") },
        placeholder = { Text("https://buddy.example.com") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(Modifier.height(8.dp))
    OutlinedTextField(
        value = state.authToken,
        onValueChange = vm::setAuthToken,
        label = { Text("Auth token") },
        singleLine = true,
        visualTransformation = PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(Modifier.height(12.dp))

    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(
            onClick = { vm.testBackend() },
            enabled = !state.testing,
            modifier = Modifier.weight(1f),
        ) {
            if (state.testing) {
                CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
                Spacer(Modifier.size(6.dp))
            }
            Text("Test connection")
        }
        Button(
            onClick = vm::next,
            enabled = state.backendValidated,
            modifier = Modifier.weight(1f),
        ) { Text("Continue") }
    }

    state.testResult?.let { msg ->
        Spacer(Modifier.height(12.dp))
        Text(
            text = msg,
            color = if (state.testError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun IntakeStep(state: OnboardingUiState, vm: OnboardingViewModel) {
    LaunchedEffect(state.step) {
        if (state.intakeId == null && !state.intakeFinished) {
            vm.startIntake()
        }
    }

    StepHeading(
        title = "Persona",
        subtitle = "Ten short questions calibrate the persona's voice. You can skip and stick with defaults; you can re-run later from Settings.",
    )
    Spacer(Modifier.height(20.dp))

    if (state.intakeQuestion != null && !state.intakeFinished) {
        Text(
            text = "Question ${state.intakeStep} of ${state.intakeTotal}",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            text = state.intakeQuestion!!,
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onBackground,
        )
        Spacer(Modifier.height(14.dp))
        // Buttons FIRST — pinned visibly above the text field so they're
        // never hidden by the soft keyboard. Reverse of the usual layout
        // intentionally.
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = vm::skipIntake, modifier = Modifier.weight(1f)) {
                Text("Skip")
            }
            Button(
                onClick = vm::submitIntakeAnswer,
                modifier = Modifier.weight(1f),
                enabled = !state.intakeSubmitting && state.intakeAnswer.isNotBlank(),
            ) {
                if (state.intakeSubmitting) {
                    CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.size(6.dp))
                }
                Text("Next →")
            }
        }
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = state.intakeAnswer,
            onValueChange = vm::setIntakeAnswer,
            placeholder = { Text("Type your answer…") },
            modifier = Modifier.fillMaxWidth().heightIn(min = 96.dp, max = 220.dp),
            maxLines = 6,
            keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
                imeAction = androidx.compose.ui.text.input.ImeAction.Send,
                capitalization = androidx.compose.ui.text.input.KeyboardCapitalization.Sentences,
            ),
            keyboardActions = androidx.compose.foundation.text.KeyboardActions(
                onSend = {
                    if (state.intakeAnswer.isNotBlank() && !state.intakeSubmitting) {
                        vm.submitIntakeAnswer()
                    }
                },
            ),
        )
    } else if (state.intakeFinished) {
        Text(
            text = "Done with the questions. Synthesizing PERSONA.md and MEMORY.md — this calls the reasoning tier and may take a few seconds.",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onBackground,
        )
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = vm::finalizeIntake,
            modifier = Modifier.fillMaxWidth(),
            enabled = !state.intakeFinalizing,
        ) {
            if (state.intakeFinalizing) {
                CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
                Spacer(Modifier.size(6.dp))
            }
            Text("Finalize persona")
        }
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = vm::skipIntake, modifier = Modifier.fillMaxWidth()) {
            Text("Skip without finalizing")
        }
    } else {
        Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RhythmStep(state: OnboardingUiState, vm: OnboardingViewModel) {
    val context = LocalContext.current
    val notifPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* ignore — toggle saves either way */ }

    StepHeading(
        title = "Daily rhythm",
        subtitle = "Morning check-in nudges you to plan the day. End-of-day prompt asks for the par-1 grade and an optional journal note.",
    )
    Spacer(Modifier.height(20.dp))

    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Daily prompts", modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
        Switch(
            checked = state.alarmsEnabled,
            onCheckedChange = { enabled ->
                if (enabled && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    if (ContextCompat.checkSelfPermission(
                            context, Manifest.permission.POST_NOTIFICATIONS
                        ) != PackageManager.PERMISSION_GRANTED
                    ) {
                        notifPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    }
                }
                vm.setAlarmsEnabled(enabled)
            },
        )
    }
    Spacer(Modifier.height(12.dp))
    TimeRow(
        label = "Morning",
        hour = state.morningHour,
        minute = state.morningMinute,
        enabled = state.alarmsEnabled,
        onPicked = vm::setMorning,
    )
    Spacer(Modifier.height(8.dp))
    TimeRow(
        label = "End of day",
        hour = state.eodHour,
        minute = state.eodMinute,
        enabled = state.alarmsEnabled,
        onPicked = vm::setEod,
    )

    Spacer(Modifier.height(20.dp))
    Button(onClick = { vm.saveRhythmAndContinue() }, modifier = Modifier.fillMaxWidth()) {
        Text("Continue")
    }
}

@Composable
private fun TimeRow(
    label: String,
    hour: Int,
    minute: Int,
    enabled: Boolean,
    onPicked: (Int, Int) -> Unit,
) {
    val context = LocalContext.current
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
        OutlinedButton(
            enabled = enabled,
            onClick = {
                TimePickerDialog(
                    context, { _, h, m -> onPicked(h, m) }, hour, minute, false,
                ).show()
            },
        ) { Text("%02d:%02d".format(hour, minute)) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FirstGoalStep(state: OnboardingUiState, vm: OnboardingViewModel) {
    StepHeading(
        title = "First goal",
        subtitle = "Optional. One concrete thing you want to track right now. You can add more from the Goals tab later.",
    )
    Spacer(Modifier.height(20.dp))

    OutlinedTextField(
        value = state.firstGoalStatement,
        onValueChange = vm::setFirstGoalStatement,
        label = { Text("Statement") },
        placeholder = { Text("e.g. Read 24 books this year") },
        modifier = Modifier.fillMaxWidth(),
    )
    Spacer(Modifier.height(8.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedTextField(
            value = state.firstGoalAmount,
            onValueChange = vm::setFirstGoalAmount,
            label = { Text("Daily target") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            modifier = Modifier.weight(1f),
        )
        OutlinedTextField(
            value = state.firstGoalUnit,
            onValueChange = vm::setFirstGoalUnit,
            label = { Text("Unit") },
            placeholder = { Text("pages, minutes…") },
            singleLine = true,
            modifier = Modifier.weight(1f),
        )
    }

    Spacer(Modifier.height(20.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(onClick = vm::next, modifier = Modifier.weight(1f)) { Text("Skip") }
        Button(
            onClick = { vm.createFirstGoalAndContinue() },
            enabled = !state.creatingGoal,
            modifier = Modifier.weight(1f),
        ) {
            if (state.creatingGoal) {
                CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(16.dp))
                Spacer(Modifier.size(6.dp))
            }
            Text(if (state.firstGoalStatement.isBlank()) "Continue" else "Add goal")
        }
    }
}

@Composable
private fun DoneStep(onFinish: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        StepHeading(
            title = "Set.",
            subtitle = "Open the chat tab anytime to talk. Tap the home-screen widget for one-tap voice capture. Adjust anything from Settings.",
        )
        Spacer(Modifier.height(28.dp))
        Button(onClick = onFinish, modifier = Modifier.fillMaxWidth()) { Text("Open Buddy") }
    }
}

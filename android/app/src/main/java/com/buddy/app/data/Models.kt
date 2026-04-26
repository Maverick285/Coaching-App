package com.buddy.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// --- Health -----------------------------------------------------------------

@Serializable
data class DailyRhythm(
    val timezone: String,
    @SerialName("morning_hour") val morningHour: Int,
    @SerialName("morning_minute") val morningMinute: Int,
    @SerialName("end_of_day_hour") val endOfDayHour: Int,
    @SerialName("end_of_day_minute") val endOfDayMinute: Int,
)

@Serializable
data class ScheduledJob(
    val id: String,
    @SerialName("next_run_at") val nextRunAt: String? = null,
    val trigger: String = "",
)

@Serializable
data class DiagnosticsBlock(
    @SerialName("last_consolidation_at") val lastConsolidationAt: String? = null,
    @SerialName("last_consolidation_status") val lastConsolidationStatus: String? = null,
    @SerialName("last_backup_push_at") val lastBackupPushAt: String? = null,
    @SerialName("last_backup_push_status") val lastBackupPushStatus: String? = null,
    @SerialName("last_engine_tick_at") val lastEngineTickAt: String? = null,
    @SerialName("last_engine_tick_fired") val lastEngineTickFired: String? = null,
    @SerialName("sms_configured") val smsConfigured: Boolean = false,
    @SerialName("git_remote_configured") val gitRemoteConfigured: Boolean = false,
    @SerialName("scheduled_jobs") val scheduledJobs: List<ScheduledJob> = emptyList(),
)

@Serializable
data class HealthResponse(
    val status: String,
    val version: String,
    @SerialName("db_connected") val dbConnected: Boolean,
    @SerialName("memory_repo_status") val memoryRepoStatus: String,
    @SerialName("models_resolved") val modelsResolved: Map<String, String>,
    @SerialName("daily_rhythm") val dailyRhythm: DailyRhythm? = null,
    val diagnostics: DiagnosticsBlock? = null,
)

@Serializable
data class UsageBucket(
    val label: String,
    @SerialName("tokens_in") val tokensIn: Int,
    @SerialName("tokens_out") val tokensOut: Int,
    @SerialName("cost_usd") val costUsd: Double,
)

@Serializable
data class UsageResponse(
    val today: UsageBucket,
    @SerialName("month_to_date") val monthToDate: UsageBucket,
    @SerialName("last_7_days") val last7Days: UsageBucket,
    @SerialName("by_model") val byModel: List<UsageBucket> = emptyList(),
    @SerialName("soft_cap_usd") val softCapUsd: Double,
    @SerialName("hard_cap_usd") val hardCapUsd: Double,
    @SerialName("soft_cap_exceeded") val softCapExceeded: Boolean,
    @SerialName("hard_cap_exceeded") val hardCapExceeded: Boolean,
)

// --- Converse ---------------------------------------------------------------

@Serializable
data class ConverseRequest(
    @SerialName("session_id") val sessionId: String? = null,
    val message: String,
    @SerialName("force_reasoning_tier") val forceReasoningTier: Boolean = false,
)

@Serializable
data class MemoryLoadedItem(
    val file: String,
    val reason: String,
    val score: Double? = null,
)

@Serializable
data class ConverseResponse(
    @SerialName("session_id") val sessionId: String,
    @SerialName("message_id") val messageId: String,
    val response: String,
    @SerialName("model_used") val modelUsed: String,
    @SerialName("tokens_in") val tokensIn: Int,
    @SerialName("tokens_out") val tokensOut: Int,
    @SerialName("cost_estimate") val costEstimate: Double,
    @SerialName("memory_loaded") val memoryLoaded: List<MemoryLoadedItem> = emptyList(),
)

// --- Conversations ----------------------------------------------------------

@Serializable
data class ConversationMessageOut(
    val id: String,
    val role: String,
    val content: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("model_used") val modelUsed: String,
)

@Serializable
data class ConversationDetail(
    @SerialName("session_id") val sessionId: String,
    @SerialName("started_at") val startedAt: String,
    val title: String,
    val messages: List<ConversationMessageOut>,
)

// --- Profile ---------------------------------------------------------------

@Serializable
data class ProfileResponse(
    @SerialName("user_name") val userName: String,
    @SerialName("persona_name") val personaName: String,
    val timezone: String,
    @SerialName("onboarding_complete") val onboardingComplete: Boolean,
    @SerialName("has_persona_md") val hasPersonaMd: Boolean,
    @SerialName("has_memory_md") val hasMemoryMd: Boolean,
)

@Serializable
data class ProfileUpdate(
    @SerialName("user_name") val userName: String? = null,
    @SerialName("persona_name") val personaName: String? = null,
    val timezone: String? = null,
)

// --- Persona intake (in-app flow) -----------------------------------------

@Serializable
data class IntakeStartResponse(
    @SerialName("intake_id") val intakeId: String,
    val question: String,
    val step: Int,
    @SerialName("total_steps") val totalSteps: Int,
)

@Serializable
data class IntakeTurnRequest(
    @SerialName("intake_id") val intakeId: String,
    val answer: String,
)

@Serializable
data class IntakeTurnResponse(
    @SerialName("intake_id") val intakeId: String,
    val question: String? = null,
    val step: Int,
    @SerialName("total_steps") val totalSteps: Int,
    val finished: Boolean,
)

@Serializable
data class IntakeFinalizeRequest(
    @SerialName("intake_id") val intakeId: String,
)

@Serializable
data class IntakeFinalizeResponse(
    @SerialName("intake_id") val intakeId: String,
    @SerialName("persona_md") val personaMd: String,
    @SerialName("memory_md") val memoryMd: String,
)

// --- Memory files (PERSONA.md / MEMORY.md / PATTERNS.md editor) ----------

@Serializable
data class MemoryFileMeta(
    val path: String,
    @SerialName("document_type") val documentType: String,
    val bytes: Int,
    @SerialName("last_modified") val lastModified: String,
    val indexed: Boolean,
)

@Serializable
data class MemoryFilesResponse(val files: List<MemoryFileMeta>)

@Serializable
data class MemoryFileContent(
    val path: String,
    val content: String,
    @SerialName("last_modified") val lastModified: String,
)

@Serializable
data class MemoryFileWrite(
    val content: String,
    @SerialName("commit_message") val commitMessage: String? = null,
)

// --- Distraction rules (per-goal Phase 4 editor) -------------------------

@Serializable
data class DistractionRule(
    val id: Int,
    @SerialName("goal_id") val goalId: Int,
    @SerialName("distractor_category") val distractorCategory: String,
    @SerialName("cooldown_seconds") val cooldownSeconds: Int,
    @SerialName("is_active") val isActive: Boolean,
)

@Serializable
data class DistractionRulesListResponse(val rules: List<DistractionRule>)

@Serializable
data class DistractionRuleCreate(
    @SerialName("goal_id") val goalId: Int,
    @SerialName("distractor_category") val distractorCategory: String,
    @SerialName("cooldown_seconds") val cooldownSeconds: Int = 90,
)

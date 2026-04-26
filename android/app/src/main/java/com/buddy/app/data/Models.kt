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
data class HealthResponse(
    val status: String,
    val version: String,
    @SerialName("db_connected") val dbConnected: Boolean,
    @SerialName("memory_repo_status") val memoryRepoStatus: String,
    @SerialName("models_resolved") val modelsResolved: Map<String, String>,
    @SerialName("daily_rhythm") val dailyRhythm: DailyRhythm? = null,
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

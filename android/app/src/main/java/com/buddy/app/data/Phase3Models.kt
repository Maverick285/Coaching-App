package com.buddy.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive

// --- Capture ---------------------------------------------------------------

@Serializable
data class CaptureAction(
    val kind: String,
    val summary: String,
    val payload: JsonObject = JsonObject(emptyMap()),
    val confidence: Double = 1.0,
)

fun CaptureAction.payloadString(key: String): String? =
    (payload[key] as? JsonPrimitive)?.contentOrNull

fun CaptureAction.payloadInt(key: String): Int? =
    (payload[key] as? JsonPrimitive)?.jsonPrimitive?.contentOrNull?.toIntOrNull()

@Serializable
data class CaptureRequest(
    val text: String,
    val source: String = "manual",
)

@Serializable
data class CaptureResponse(
    @SerialName("capture_id") val captureId: Int,
    @SerialName("raw_text") val rawText: String,
    val actions: List<CaptureAction> = emptyList(),
    @SerialName("fallback_message") val fallbackMessage: String = "",
)

@Serializable
data class CaptureConfirm(
    @SerialName("capture_id") val captureId: Int,
    val actions: List<CaptureAction>,
)

@Serializable
data class DispatchResultItem(
    val kind: String,
    val success: Boolean,
    val detail: String = "",
    @SerialName("created_id") val createdId: Int? = null,
)

@Serializable
data class CaptureDispatchResponse(
    @SerialName("capture_id") val captureId: Int,
    val results: List<DispatchResultItem>,
)

// --- Focus sessions --------------------------------------------------------

@Serializable
data class FocusSession(
    val id: Int,
    @SerialName("goal_id") val goalId: Int? = null,
    val intention: String,
    @SerialName("started_at") val startedAt: String,
    @SerialName("planned_duration_minutes") val plannedDurationMinutes: Int,
    @SerialName("ended_at") val endedAt: String? = null,
    val state: String,
    val summary: String = "",
    @SerialName("interventions_fired") val interventionsFired: Int = 0,
)

@Serializable
data class FocusActiveResponse(val session: FocusSession? = null)

@Serializable
data class FocusStart(
    val intention: String,
    @SerialName("planned_duration_minutes") val plannedDurationMinutes: Int = 45,
    @SerialName("goal_id") val goalId: Int? = null,
)

@Serializable
data class FocusEnd(
    val summary: String = "",
    val state: String = "completed",
)

@Serializable
data class FocusCheckIn(
    val id: Int,
    @SerialName("session_id") val sessionId: Int,
    @SerialName("fired_at") val firedAt: String,
    val kind: String,
    val message: String,
    @SerialName("user_response") val userResponse: String = "",
)

@Serializable
data class FocusCheckInResponse(
    @SerialName("check_in") val checkIn: FocusCheckIn,
)

@Serializable
data class FocusSessionDetail(
    val session: FocusSession,
    @SerialName("check_ins") val checkIns: List<FocusCheckIn> = emptyList(),
)

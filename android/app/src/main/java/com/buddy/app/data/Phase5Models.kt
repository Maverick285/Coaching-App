package com.buddy.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// --- Blocked-app rules (Tier 3 friction / Tier 4 hard block) ---------------

@Serializable
data class BlockedAppRule(
    val id: Int,
    @SerialName("goal_id") val goalId: Int,
    @SerialName("package_name") val packageName: String,
    @SerialName("block_tier") val blockTier: Int,
    @SerialName("is_active") val isActive: Boolean,
)

@Serializable
data class BlockedAppRuleCreate(
    @SerialName("goal_id") val goalId: Int,
    @SerialName("package_name") val packageName: String,
    @SerialName("block_tier") val blockTier: Int = 3,
)

@Serializable
data class BlockedAppRulesListResponse(val rules: List<BlockedAppRule>)

@Serializable
data class ActiveBlock(
    @SerialName("package_name") val packageName: String,
    @SerialName("block_tier") val blockTier: Int,
    @SerialName("goal_id") val goalId: Int,
    @SerialName("session_id") val sessionId: Int,
)

@Serializable
data class ActiveBlocksResponse(
    val blocks: List<ActiveBlock> = emptyList(),
    @SerialName("override_window_open") val overrideWindowOpen: Boolean = false,
    @SerialName("override_expires_at") val overrideExpiresAt: String? = null,
)

// --- Override system -------------------------------------------------------

@Serializable
data class OverrideRequestCreate(
    @SerialName("package_name") val packageName: String,
    val reason: String,
    @SerialName("session_id") val sessionId: Int? = null,
    @SerialName("goal_id") val goalId: Int? = null,
    @SerialName("intervention_id") val interventionId: Int? = null,
    @SerialName("active_minutes") val activeMinutes: Int = 15,
)

@Serializable
data class OverrideRequest(
    val id: Int,
    @SerialName("requested_at") val requestedAt: String,
    @SerialName("session_id") val sessionId: Int? = null,
    @SerialName("goal_id") val goalId: Int? = null,
    @SerialName("intervention_id") val interventionId: Int? = null,
    @SerialName("package_name") val packageName: String,
    val reason: String,
    @SerialName("approver_label") val approverLabel: String,
    @SerialName("sms_status") val smsStatus: String,
    @SerialName("sms_detail") val smsDetail: String,
    val status: String,
    @SerialName("redeemed_at") val redeemedAt: String? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
    @SerialName("active_minutes") val activeMinutes: Int,
    @SerialName("code_dev_echo") val codeDevEcho: String? = null,
)

@Serializable
data class OverrideRedeemRequest(val code: String)

@Serializable
data class OverrideRedeemResponse(
    val request: OverrideRequest,
    val success: Boolean,
    val message: String,
)

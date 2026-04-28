package com.buddy.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// --- Goals -----------------------------------------------------------------

@Serializable
data class Goal(
    val id: Int,
    val statement: String,
    val timeframe: String,
    val deadline: String? = null,
    val priority: Int,
    val approach: String,
    @SerialName("plan_source") val planSource: String,
    val state: String,
    @SerialName("intervention_ceiling") val interventionCeiling: Int,
    @SerialName("pace_target_unit") val paceTargetUnit: String,
    @SerialName("pace_target_amount") val paceTargetAmount: Double,
    @SerialName("pace_target_description") val paceTargetDescription: String,
    @SerialName("mvp_threshold") val mvpThreshold: String,
    @SerialName("parent_goal_id") val parentGoalId: Int? = null,
    @SerialName("reflection_log") val reflectionLog: String,
    @SerialName("stake_webhook_url") val stakeWebhookUrl: String? = null,
    @SerialName("stake_webhook_secret") val stakeWebhookSecret: String? = null,
    @SerialName("stake_active") val stakeActive: Boolean = false,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class GoalsListResponse(val goals: List<Goal>)

@Serializable
data class GoalCreate(
    val statement: String,
    val priority: Int = 3,
    @SerialName("pace_target_unit") val paceTargetUnit: String = "",
    @SerialName("pace_target_amount") val paceTargetAmount: Double = 0.0,
    @SerialName("pace_target_description") val paceTargetDescription: String = "",
    @SerialName("mvp_threshold") val mvpThreshold: String = "",
    val approach: String = "user_driven",
    @SerialName("plan_source") val planSource: String = "user_plan",
    val timeframe: String = "open_ended",
    val deadline: String? = null,
    @SerialName("intervention_ceiling") val interventionCeiling: Int = 2,
    @SerialName("parent_goal_id") val parentGoalId: Int? = null,
    @SerialName("stake_webhook_url") val stakeWebhookUrl: String? = null,
    @SerialName("stake_webhook_secret") val stakeWebhookSecret: String? = null,
    @SerialName("stake_active") val stakeActive: Boolean = false,
)

@Serializable
data class GoalUpdate(
    val state: String? = null,
    val priority: Int? = null,
    val statement: String? = null,
    val timeframe: String? = null,
    val deadline: String? = null,
    val approach: String? = null,
    @SerialName("intervention_ceiling") val interventionCeiling: Int? = null,
    @SerialName("pace_target_amount") val paceTargetAmount: Double? = null,
    @SerialName("pace_target_unit") val paceTargetUnit: String? = null,
    @SerialName("pace_target_description") val paceTargetDescription: String? = null,
    @SerialName("mvp_threshold") val mvpThreshold: String? = null,
)

@Serializable
data class Task(
    val id: Int,
    @SerialName("goal_id") val goalId: Int,
    val description: String,
    @SerialName("definition_of_done") val definitionOfDone: String,
    @SerialName("estimated_duration_minutes") val estimatedDurationMinutes: Int? = null,
    @SerialName("actual_duration_minutes") val actualDurationMinutes: Int? = null,
    @SerialName("scheduled_at") val scheduledAt: String? = null,
    @SerialName("triggering_intention_id") val triggeringIntentionId: Int? = null,
    val state: String,
    @SerialName("first_60_seconds") val first60Seconds: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("completed_at") val completedAt: String? = null,
)

@Serializable
data class TasksListResponse(val tasks: List<Task>)

@Serializable
data class TaskCreate(
    @SerialName("goal_id") val goalId: Int,
    val description: String,
    @SerialName("definition_of_done") val definitionOfDone: String = "",
    @SerialName("estimated_duration_minutes") val estimatedDurationMinutes: Int? = null,
    @SerialName("first_60_seconds") val first60Seconds: String = "",
)

@Serializable
data class TaskUpdate(
    val state: String? = null,
    val description: String? = null,
    @SerialName("first_60_seconds") val first60Seconds: String? = null,
    @SerialName("scheduled_at") val scheduledAt: String? = null,
    @SerialName("estimated_duration_minutes") val estimatedDurationMinutes: Int? = null,
)

@Serializable
data class TaskBatchNLRequest(
    val text: String,
    val source: String = "text",
)

@Serializable
data class TaskBatchOpResult(
    val op: String,
    val status: String,
    @SerialName("task_id") val taskId: Int? = null,
    val detail: String = "",
)

@Serializable
data class TaskBatchNLResponse(
    @SerialName("parsed_ops") val parsedOps: List<kotlinx.serialization.json.JsonObject> = emptyList(),
    val results: List<TaskBatchOpResult> = emptyList(),
    @SerialName("raw_text") val rawText: String = "",
)

// --- Goal planner (wish -> structured plan) ---------------------------------

@Serializable
data class GoalPlanRequest(
    val wish: String,
    val deadline: String? = null,
)

@Serializable
data class PlannedMilestone(
    val statement: String,
    val deadline: String? = null,
    @SerialName("pace_target_unit") val paceTargetUnit: String = "",
    @SerialName("pace_target_amount") val paceTargetAmount: Double = 0.0,
    @SerialName("mvp_threshold") val mvpThreshold: String = "",
)

@Serializable
data class PlannedTask(
    val description: String,
    @SerialName("estimated_duration_minutes") val estimatedDurationMinutes: Int? = null,
    @SerialName("first_60_seconds") val first60Seconds: String = "",
    @SerialName("scheduled_at") val scheduledAt: String? = null,
)

@Serializable
data class PlannedIntention(
    @SerialName("cue_type") val cueType: String,
    @SerialName("cue_text") val cueText: String,
    @SerialName("response_text") val responseText: String,
)

@Serializable
data class GoalPlan(
    val statement: String,
    val rationale: String = "",
    @SerialName("user_facing_summary") val userFacingSummary: String = "",
    @SerialName("pace_target_unit") val paceTargetUnit: String,
    @SerialName("pace_target_amount") val paceTargetAmount: Double,
    @SerialName("pace_target_description") val paceTargetDescription: String = "",
    @SerialName("mvp_threshold") val mvpThreshold: String = "",
    @SerialName("intervention_ceiling") val interventionCeiling: Int = 2,
    val approach: String = "hybrid",
    val priority: Int = 3,
    val deadline: String? = null,
    val milestones: List<PlannedMilestone> = emptyList(),
    @SerialName("first_week_tasks") val firstWeekTasks: List<PlannedTask> = emptyList(),
    @SerialName("implementation_intentions") val implementationIntentions: List<PlannedIntention> = emptyList(),
    val obstacles: List<String> = emptyList(),
    @SerialName("outcome_vision") val outcomeVision: String = "",
)

@Serializable
data class GoalPlanResponse(
    val plan: GoalPlan,
    @SerialName("raw_response") val rawResponse: String = "",
)

@Serializable
data class GoalPlanApplyRequest(val plan: GoalPlan)

@Serializable
data class GoalPlanApplyResponse(
    @SerialName("goal_id") val goalId: Int,
    @SerialName("milestone_ids") val milestoneIds: List<Int> = emptyList(),
    @SerialName("task_ids") val taskIds: List<Int> = emptyList(),
    @SerialName("intention_ids") val intentionIds: List<Int> = emptyList(),
)

@Serializable
data class Intention(
    val id: Int,
    @SerialName("goal_id") val goalId: Int? = null,
    @SerialName("task_id") val taskId: Int? = null,
    @SerialName("cue_type") val cueType: String,
    @SerialName("cue_text") val cueText: String,
    @SerialName("response_text") val responseText: String,
    @SerialName("is_active") val isActive: Boolean,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class IntentionCreate(
    @SerialName("goal_id") val goalId: Int? = null,
    @SerialName("task_id") val taskId: Int? = null,
    @SerialName("cue_type") val cueType: String,
    @SerialName("cue_text") val cueText: String,
    @SerialName("response_text") val responseText: String,
)

@Serializable
data class GoalDetail(
    val goal: Goal,
    val tasks: List<Task> = emptyList(),
    val intentions: List<Intention> = emptyList(),
    @SerialName("today_progress") val todayProgress: Double = 0.0,
    @SerialName("today_grade") val todayGrade: Double = 0.0,
)

// --- WOOP ------------------------------------------------------------------

@Serializable
data class WoopRequest(
    val wish: String,
    @SerialName("initial_obstacle") val initialObstacle: String? = null,
    @SerialName("desired_pace_unit") val desiredPaceUnit: String? = null,
)

@Serializable
data class WoopResponse(
    val wish: String,
    val outcome: String,
    val obstacles: List<String> = emptyList(),
    val plan: List<String> = emptyList(),
    @SerialName("suggested_intentions") val suggestedIntentions: List<IntentionCreate> = emptyList(),
    @SerialName("suggested_tasks") val suggestedTasks: List<String> = emptyList(),
    @SerialName("suggested_pace_unit") val suggestedPaceUnit: String = "",
    @SerialName("suggested_pace_amount") val suggestedPaceAmount: Double = 0.0,
    @SerialName("suggested_pace_description") val suggestedPaceDescription: String = "",
)

// --- Progress --------------------------------------------------------------

@Serializable
data class ProgressLogCreate(
    @SerialName("goal_id") val goalId: Int,
    @SerialName("attributed_units") val attributedUnits: Double,
    @SerialName("unit_label") val unitLabel: String = "",
    @SerialName("raw_text") val rawText: String = "",
    val source: String = "manual",
    val note: String = "",
)

@Serializable
data class ProgressLog(
    val id: Int,
    @SerialName("goal_id") val goalId: Int,
    @SerialName("recorded_at") val recordedAt: String,
    @SerialName("raw_text") val rawText: String,
    @SerialName("attributed_units") val attributedUnits: Double,
    @SerialName("unit_label") val unitLabel: String,
    val source: String,
    val confidence: Double,
    val note: String,
)

@Serializable
data class ProgressFreeForm(val text: String, val source: String = "manual")

@Serializable
data class AttributedProgress(
    @SerialName("goal_id") val goalId: Int,
    val units: Double,
    @SerialName("unit_label") val unitLabel: String,
    val confidence: Double,
    val rationale: String,
)

@Serializable
data class ProgressFreeFormResponse(
    val attributions: List<AttributedProgress> = emptyList(),
    val logged: List<ProgressLog> = emptyList(),
    @SerialName("unattributed_text") val unattributedText: String = "",
)

// --- Day grade -------------------------------------------------------------

@Serializable
data class PerGoalGrade(
    @SerialName("goal_id") val goalId: Int,
    val statement: String,
    @SerialName("pace_target_amount") val paceTargetAmount: Double,
    @SerialName("pace_target_unit") val paceTargetUnit: String,
    @SerialName("progress_today") val progressToday: Double,
    val score: Double,
)

@Serializable
data class DayGrade(
    @SerialName("grade_date") val gradeDate: String,
    @SerialName("system_score") val systemScore: Double,
    @SerialName("user_score") val userScore: Double? = null,
    @SerialName("per_goal") val perGoal: List<PerGoalGrade> = emptyList(),
    val explanation: String = "",
    @SerialName("user_notes") val userNotes: String = "",
    @SerialName("is_zero_day") val isZeroDay: Boolean = false,
    val finalized: Boolean = false,
    @SerialName("computed_at") val computedAt: String,
)

@Serializable
data class DayGradeFinalize(
    @SerialName("user_score") val userScore: Double? = null,
    @SerialName("user_notes") val userNotes: String = "",
    @SerialName("accept_system_score") val acceptSystemScore: Boolean = true,
)

// --- Streak ----------------------------------------------------------------

@Serializable
data class StreakDay(
    val date: String,
    val score: Double,
    @SerialName("is_zero") val isZero: Boolean,
    @SerialName("is_pause") val isPause: Boolean,
)

@Serializable
data class StreakResponse(
    @SerialName("current_streak_length") val currentStreakLength: Int,
    @SerialName("pause_days") val pauseDays: List<String> = emptyList(),
    @SerialName("last_zero_day") val lastZeroDay: String? = null,
    val history: List<StreakDay> = emptyList(),
)

// --- Weekly review ---------------------------------------------------------

@Serializable
data class WeeklyReviewBucket(val label: String, val count: Int)

@Serializable
data class GoalPaceSummary(
    @SerialName("goal_id") val goalId: Int,
    val statement: String,
    @SerialName("average_pace") val averagePace: Double,
    @SerialName("days_active") val daysActive: Int,
    @SerialName("days_zero") val daysZero: Int,
)

@Serializable
data class WeeklyReviewResponse(
    @SerialName("week_start") val weekStart: String,
    @SerialName("week_end") val weekEnd: String,
    @SerialName("average_day_grade") val averageDayGrade: Double,
    val distribution: List<WeeklyReviewBucket> = emptyList(),
    @SerialName("per_goal") val perGoal: List<GoalPaceSummary> = emptyList(),
    @SerialName("pattern_observations") val patternObservations: List<String> = emptyList(),
    @SerialName("journal_excerpts") val journalExcerpts: List<String> = emptyList(),
    @SerialName("suggested_adjustments") val suggestedAdjustments: List<String> = emptyList(),
)

// --- Journal ---------------------------------------------------------------

@Serializable
data class JournalEntry(
    @SerialName("entry_date") val entryDate: String,
    val content: String,
    val mood: String,
    val tags: List<String> = emptyList(),
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class JournalListResponse(val entries: List<JournalEntry>)

@Serializable
data class JournalEntryWrite(
    val content: String = "",
    val mood: String = "",
    val tags: List<String> = emptyList(),
)

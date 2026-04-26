package com.buddy.app.data

import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface BuddyApi {

    @GET("/health")
    suspend fun health(): HealthResponse

    @POST("/converse")
    suspend fun converse(@Body req: ConverseRequest): ConverseResponse

    @GET("/conversations/{sessionId}")
    suspend fun conversation(@Path("sessionId") sessionId: String): ConversationDetail

    // --- Goals -------------------------------------------------------------

    @GET("/goals")
    suspend fun listGoals(@Query("state") state: String? = null): GoalsListResponse

    @POST("/goals")
    suspend fun createGoal(@Body req: GoalCreate): Goal

    @GET("/goals/{id}")
    suspend fun getGoal(@Path("id") id: Int): GoalDetail

    @PATCH("/goals/{id}")
    suspend fun updateGoal(@Path("id") id: Int, @Body req: GoalUpdate): Goal

    @DELETE("/goals/{id}")
    suspend fun deleteGoal(@Path("id") id: Int)

    @POST("/goals/woop")
    suspend fun runWoop(@Body req: WoopRequest): WoopResponse

    // --- Tasks -------------------------------------------------------------

    @GET("/tasks")
    suspend fun listTasks(
        @Query("goal_id") goalId: Int? = null,
        @Query("state") state: String? = null,
    ): TasksListResponse

    @POST("/tasks")
    suspend fun createTask(@Body req: TaskCreate): Task

    @PATCH("/tasks/{id}")
    suspend fun updateTask(@Path("id") id: Int, @Body req: TaskUpdate): Task

    @DELETE("/tasks/{id}")
    suspend fun deleteTask(@Path("id") id: Int)

    // --- Intentions --------------------------------------------------------

    @POST("/intentions")
    suspend fun createIntention(@Body req: IntentionCreate): Intention

    // --- Progress ----------------------------------------------------------

    @POST("/progress/log")
    suspend fun logProgress(@Body req: ProgressLogCreate): ProgressLog

    @POST("/progress/freeform")
    suspend fun logFreeform(@Body req: ProgressFreeForm): ProgressFreeFormResponse

    // --- Grade -------------------------------------------------------------

    @GET("/grade/today")
    suspend fun gradeToday(): DayGrade

    @GET("/grade/{day}")
    suspend fun gradeFor(@Path("day") day: String): DayGrade

    @POST("/grade/{day}/finalize")
    suspend fun finalizeGrade(
        @Path("day") day: String,
        @Body req: DayGradeFinalize,
    ): DayGrade

    @GET("/streak")
    suspend fun streak(@Query("days") days: Int = 30): StreakResponse

    @GET("/weekly-review")
    suspend fun weeklyReview(@Query("week_offset") offset: Int = 0): WeeklyReviewResponse

    // --- Journal -----------------------------------------------------------

    @GET("/journal")
    suspend fun listJournal(@Query("limit") limit: Int = 30): JournalListResponse

    @GET("/journal/{day}")
    suspend fun getJournal(@Path("day") day: String): JournalEntry

    @PUT("/journal/{day}")
    suspend fun upsertJournal(
        @Path("day") day: String,
        @Body req: JournalEntryWrite,
    ): JournalEntry

    // --- Phase 3: capture --------------------------------------------------

    @POST("/capture")
    suspend fun capture(@Body req: CaptureRequest): CaptureResponse

    @POST("/capture/confirm")
    suspend fun captureConfirm(@Body req: CaptureConfirm): CaptureDispatchResponse

    // --- Phase 3: focus sessions ------------------------------------------

    @POST("/focus/start")
    suspend fun startFocus(@Body req: FocusStart): FocusSession

    @POST("/focus/{id}/end")
    suspend fun endFocus(@Path("id") id: Int, @Body req: FocusEnd): FocusSession

    @GET("/focus/active")
    suspend fun activeFocus(): FocusActiveResponse

    @GET("/focus/{id}")
    suspend fun focusDetail(@Path("id") id: Int): FocusSessionDetail

    @POST("/focus/{id}/check-in")
    suspend fun fireCheckIn(
        @Path("id") id: Int,
        @Query("kind") kind: String = "presence",
    ): FocusCheckInResponse

    @GET("/focus/recent")
    suspend fun recentFocus(@Query("limit") limit: Int = 20): List<FocusSession>
}

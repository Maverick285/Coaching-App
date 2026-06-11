package com.buddy.app.data

class ProductivityRepository(val api: BuddyApi) {

    // Goals
    suspend fun listGoals(state: String? = null) = api.listGoals(state)
    suspend fun createGoal(req: GoalCreate) = api.createGoal(req)
    suspend fun getGoal(id: Int) = api.getGoal(id)
    suspend fun updateGoal(id: Int, req: GoalUpdate) = api.updateGoal(id, req)
    suspend fun deleteGoal(id: Int) = api.deleteGoal(id)
    suspend fun runWoop(req: WoopRequest) = api.runWoop(req)

    // Tasks
    suspend fun listTasks(goalId: Int? = null, state: String? = null) =
        api.listTasks(goalId, state)
    suspend fun createTask(req: TaskCreate) = api.createTask(req)
    suspend fun updateTask(id: Int, req: TaskUpdate) = api.updateTask(id, req)
    suspend fun deleteTask(id: Int) = api.deleteTask(id)

    // Intentions
    suspend fun createIntention(req: IntentionCreate) = api.createIntention(req)

    // Progress
    suspend fun logProgress(req: ProgressLogCreate) = api.logProgress(req)
    suspend fun logFreeform(text: String) = api.logFreeform(ProgressFreeForm(text))

    // Grade / streak / weekly
    suspend fun gradeToday() = api.gradeToday()
    suspend fun gradeFor(day: String) = api.gradeFor(day)
    suspend fun finalizeGrade(day: String, req: DayGradeFinalize) =
        api.finalizeGrade(day, req)
    suspend fun streak(days: Int = 30) = api.streak(days)
    suspend fun weeklyReview() = api.weeklyReview()

    // Journal
    suspend fun getJournal(day: String) = api.getJournal(day)
    suspend fun upsertJournal(day: String, req: JournalEntryWrite) =
        api.upsertJournal(day, req)
    suspend fun listJournal(limit: Int = 30) = api.listJournal(limit)
}

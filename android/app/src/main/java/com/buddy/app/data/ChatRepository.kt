package com.buddy.app.data

/** Thin domain wrapper around [BuddyApi] so the ViewModel doesn't see Retrofit. */
class ChatRepository(private val api: BuddyApi) {

    suspend fun loadHistory(sessionId: String): ConversationDetail =
        api.conversation(sessionId)

    suspend fun send(
        sessionId: String?,
        message: String,
        forceReasoning: Boolean = false,
    ): ConverseResponse =
        api.converse(
            ConverseRequest(
                sessionId = sessionId,
                message = message,
                forceReasoningTier = forceReasoning,
            )
        )

    suspend fun health(): HealthResponse = api.health()
}

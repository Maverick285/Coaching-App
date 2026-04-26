package com.buddy.app.data

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface BuddyApi {

    @GET("/health")
    suspend fun health(): HealthResponse

    @POST("/converse")
    suspend fun converse(@Body req: ConverseRequest): ConverseResponse

    @GET("/conversations/{sessionId}")
    suspend fun conversation(@Path("sessionId") sessionId: String): ConversationDetail
}

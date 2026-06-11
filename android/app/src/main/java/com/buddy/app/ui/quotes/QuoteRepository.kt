package com.buddy.app.ui.quotes

import android.content.Context
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class Quote(
    val text: String,
    val author: String,
)

@Serializable
private data class QuotesFile(
    @SerialName("_note") val note: String? = null,
    val quotes: List<Quote> = emptyList(),
)

/**
 * Loads the curated quotes from `assets/quotes.json` once per process and
 * picks one at random. Adding more is a one-line edit to the JSON.
 */
object QuoteRepository {

    private val json = Json { ignoreUnknownKeys = true }

    @Volatile
    private var cached: List<Quote>? = null

    private fun load(context: Context): List<Quote> {
        cached?.let { return it }
        val raw = try {
            context.assets.open("quotes.json").use { it.readBytes().decodeToString() }
        } catch (_: Exception) {
            return emptyList()
        }
        return runCatching { json.decodeFromString<QuotesFile>(raw).quotes }
            .getOrElse { emptyList() }
            .also { cached = it }
    }

    fun pickRandom(context: Context): Quote? {
        val list = load(context)
        if (list.isEmpty()) return null
        return list.random()
    }
}

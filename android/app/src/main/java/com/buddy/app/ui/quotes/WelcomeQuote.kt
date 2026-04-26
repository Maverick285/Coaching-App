package com.buddy.app.ui.quotes

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/**
 * Editorial loading/welcome card. Picks one quote at random per composition
 * (so revisiting the empty state shows a fresh one).
 */
@Composable
fun WelcomeQuote(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val quote = remember { QuoteRepository.pickRandom(context) } ?: return

    Column(
        modifier = modifier
            .fillMaxWidth()
            .widthIn(max = 480.dp)
            .padding(horizontal = 24.dp, vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            text = "“${quote.text}”",
            style = MaterialTheme.typography.headlineSmall,
            fontStyle = FontStyle.Italic,
            color = MaterialTheme.colorScheme.onBackground,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(14.dp))
        Text(
            text = "— ${quote.author}",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}

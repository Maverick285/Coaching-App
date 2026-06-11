package com.buddy.app.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Editorial dark palette. Warm off-white type on near-black, with a single
 * muted clay accent. The intent is "premium hardcover, not Material default".
 */

// Surfaces
val Background = Color(0xFF0E0E0F)        // ink black, slight warmth
val Surface = Color(0xFF15161A)           // a hair lifted from background
val SurfaceVariant = Color(0xFF1F2026)    // for chips, dividers, secondary cards

// Type
val OnSurface = Color(0xFFE9E3D6)         // warm off-white, like newsprint
val OnSurfaceMuted = Color(0xFF9C9588)    // dimmed for labels, captions
val OnSurfaceFaint = Color(0xFF6E6859)    // very muted for inert metadata

// Accent — a single restrained clay/terracotta. Used sparingly.
val Primary = Color(0xFFC78A5C)
val OnPrimary = Color(0xFF15110D)

// Conversation bubbles
val UserBubble = Color(0xFF222328)        // soft contrast, not flashy
val AssistantBubble = Color(0xFF181A1F)   // sits just above the surface

// Status
val Error = Color(0xFFD3705F)             // muted brick, not Material red
val Caution = Color(0xFFCDB67A)           // warm yellow for soft warnings

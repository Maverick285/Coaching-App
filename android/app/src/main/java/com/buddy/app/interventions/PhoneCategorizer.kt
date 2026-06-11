package com.buddy.app.interventions

/**
 * Maps Android package names to the canonical category set the backend
 * understands. Mirrors pc_agent/categories/default_map.json but slimmer —
 * the phone has fewer "work" categories worth distinguishing.
 *
 * If you find yourself wanting to distinguish a new app, add the package
 * name here (find it via `adb shell pm list packages | grep <vendor>`).
 */
object PhoneCategorizer {

    private val mapping: Map<String, String> = mapOf(
        // browsers
        "com.android.chrome" to "browser",
        "com.chrome.beta" to "browser",
        "org.mozilla.firefox" to "browser",
        "com.brave.browser" to "browser",
        "com.opera.browser" to "browser",
        "com.duckduckgo.mobile.android" to "browser",

        // social media
        "com.twitter.android" to "social_media",
        "com.x.android" to "social_media",
        "com.reddit.frontpage" to "social_media",
        "com.instagram.android" to "social_media",
        "com.facebook.katana" to "social_media",
        "com.facebook.lite" to "social_media",
        "com.snapchat.android" to "social_media",
        "com.zhiliaoapp.musically" to "social_media", // TikTok
        "com.tumblr" to "social_media",
        "com.pinterest" to "social_media",
        "com.linkedin.android" to "social_media",
        "com.bsky.app" to "social_media",
        "com.threads.android" to "social_media",

        // video
        "com.google.android.youtube" to "video",
        "com.netflix.mediaclient" to "video",
        "com.amazon.avod.thirdpartyclient" to "video",
        "com.disney.disneyplus" to "video",
        "com.hulu.plus" to "video",
        "tv.twitch.android.app" to "video",
        "org.videolan.vlc" to "video",

        // music
        "com.spotify.music" to "music",
        "com.apple.android.music" to "music",
        "com.google.android.apps.youtube.music" to "music",

        // communication
        "com.slack" to "communication",
        "com.discord" to "communication",
        "com.microsoft.teams" to "communication",
        "us.zoom.videomeetings" to "communication",
        "com.google.android.gm" to "communication", // Gmail
        "com.microsoft.outlook" to "communication",
        "com.whatsapp" to "communication",
        "org.thoughtcrime.securesms" to "communication", // Signal
        "org.telegram.messenger" to "communication",

        // gaming (a starter list; add more as needed)
        "com.activision.callofduty.shooter" to "gaming",
        "com.king.candycrushsaga" to "gaming",
        "com.supercell.clashofclans" to "gaming",

        // system / launcher / settings
        "com.android.settings" to "system",
        "com.google.android.apps.nexuslauncher" to "system",
        "com.sec.android.app.launcher" to "system",
        "com.android.systemui" to "system",
    )

    /** Returns one of KNOWN_CATEGORIES (matches the backend taxonomy). */
    fun categorize(packageName: String?): String {
        if (packageName.isNullOrBlank()) return "idle"
        return mapping[packageName] ?: "other"
    }
}

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

import java.util.Properties

// Read backend defaults from local.properties (gitignored). Used to bake
// the bearer token + backend URL into the APK so reinstalls don't lose
// them. Falls back to empty strings if the keys aren't set; the user can
// always override via Settings.
val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
val defaultBackendUrl: String = localProps.getProperty("buddy.backend.url", "")
val defaultAuthToken: String = localProps.getProperty("buddy.auth.token", "")
// Bump when you rotate the embedded URL or token — installed APKs will
// then overwrite their stored values with the new defaults on next launch.
val defaultsVersion: Int = (localProps.getProperty("buddy.defaults.version") ?: "1").toInt()

android {
    namespace = "com.buddy.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.buddy.app"
        minSdk = 28
        targetSdk = 34
        versionCode = 2
        versionName = "0.1.1"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables { useSupportLibrary = true }

        buildConfigField("String", "DEFAULT_BACKEND_URL", "\"${defaultBackendUrl}\"")
        buildConfigField("String", "DEFAULT_AUTH_TOKEN", "\"${defaultAuthToken}\"")
        buildConfigField("int", "DEFAULTS_VERSION", "${defaultsVersion}")
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            isDebuggable = true
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }

    // Robolectric needs Android resources packaged into the test
    // classpath. Without `includeAndroidResources = true`, Compose
    // tests that resolve `MaterialTheme` (every one of ours) blow up
    // looking for `android.content.res.Resources`. Returning default
    // values keeps tests fast without an emulator.
    testOptions {
        unitTests {
            isIncludeAndroidResources = true
            isReturnDefaultValues = true
        }
    }
}

dependencies {
    // AndroidX core
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.datastore.preferences)

    // Compose
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    debugImplementation(libs.androidx.compose.ui.tooling)

    // Networking
    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.kotlinx.serialization.json)

    // Coroutines
    implementation(libs.kotlinx.coroutines.android)

    // Test — Robolectric + Compose UI test on the JVM (no emulator).
    // Catches runtime crashes-on-screen-mount that compile fine
    // (e.g. unresolved Compose APIs, NPE in initial recompose, ViewModel
    // wiring errors). The emulator-based androidTest sourceSet stays
    // for instrumentation tests if we ever add them.
    testImplementation(libs.junit)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.core)
    testImplementation(libs.androidx.test.runner)
    testImplementation(libs.androidx.test.rules)
    testImplementation(platform(libs.androidx.compose.bom))
    testImplementation(libs.androidx.compose.ui.test.junit4)
    testImplementation(libs.kotlinx.coroutines.android)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    androidTestImplementation(libs.androidx.junit)
}

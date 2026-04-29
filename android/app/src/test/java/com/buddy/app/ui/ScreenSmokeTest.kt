package com.buddy.app.ui

import android.app.Application
import androidx.compose.material3.Surface
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.test.core.app.ApplicationProvider
import com.buddy.app.ui.chat.ChatScreen
import com.buddy.app.ui.dreams.DreamsScreen
import com.buddy.app.ui.goals.BacklogScreen
import com.buddy.app.ui.goals.GoalsScreen
import com.buddy.app.ui.theme.BuddyTheme
import com.buddy.app.ui.today.TodayScreen
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * JVM smoke harness for every top-level Compose screen.
 *
 * The point: catch the "compiles fine, crashes at runtime" class of
 * bug that I shipped repeatedly and you experienced as unresponsive
 * nav buttons. Each test mounts a screen, lets composition settle,
 * and asserts the resulting node tree has *something* in it. If
 * composition throws (NPE, unresolved Compose API, missing string
 * resource, theme misconfiguration), `waitForIdle` propagates the
 * exception and the test fails loud.
 *
 * Where this harness draws its line:
 *   - It will catch crashes during initial composition.
 *   - It will catch screens that render an empty Surface because of
 *     a wiring bug.
 *   - It will NOT catch async errors swallowed by runCatching, real
 *     network failures, gesture-handling bugs, or ART-only quirks
 *     that don't reproduce on the JVM.
 *
 * That's a useful 70% — not 100%. Worth running before every push.
 *
 * Pre-push command:
 *   cd android && ./gradlew :app:testDebugUnitTest \
 *     --tests com.buddy.app.ui.ScreenSmokeTest
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33], application = Application::class)
class ScreenSmokeTest {
    @get:Rule
    val composeTestRule = createComposeRule()

    private fun assertScreenMounted() {
        composeTestRule.waitForIdle()
        // If composition threw, waitForIdle would already have
        // propagated. The remaining failure mode is a totally empty
        // screen, which is its own bug — assert at least one
        // semantic node exists below the test root.
        val root = composeTestRule.onRoot().fetchSemanticsNode()
        check(root.children.isNotEmpty()) {
            "screen mounted but produced no semantic nodes"
        }
    }

    @Test
    fun todayScreen() {
        composeTestRule.setContent {
            BuddyTheme {
                Surface {
                    TodayScreen(
                        onOpenGoals = {},
                        onOpenChat = {},
                        onOpenFocus = {},
                        onOpenSettings = {},
                        onOpenCustomize = {},
                        onOpenGoalDetail = {},
                    )
                }
            }
        }
        assertScreenMounted()
    }

    @Test
    fun goalsScreen() {
        composeTestRule.setContent {
            BuddyTheme {
                Surface {
                    GoalsScreen(
                        onGoalClicked = {},
                        onTalkItThrough = {},
                        onOpenBacklog = {},
                    )
                }
            }
        }
        assertScreenMounted()
    }

    @Test
    fun chatScreen() {
        composeTestRule.setContent {
            BuddyTheme {
                Surface {
                    ChatScreen(onOpenSettings = {})
                }
            }
        }
        assertScreenMounted()
    }

    @Test
    fun dreamsScreen() {
        composeTestRule.setContent {
            BuddyTheme {
                Surface {
                    DreamsScreen()
                }
            }
        }
        assertScreenMounted()
    }

    @Test
    fun backlogScreen() {
        composeTestRule.setContent {
            BuddyTheme {
                Surface {
                    BacklogScreen(onBack = {}, onGoalClicked = {})
                }
            }
        }
        assertScreenMounted()
    }

    @Suppress("unused")
    private val app: Application = ApplicationProvider.getApplicationContext()
}

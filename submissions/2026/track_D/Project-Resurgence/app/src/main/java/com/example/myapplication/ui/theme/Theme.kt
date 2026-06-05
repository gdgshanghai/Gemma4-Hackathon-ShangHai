package com.example.myapplication.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val DarkColorScheme = darkColorScheme(
    primary = SurvivalGreen,
    secondary = PureWhite,
    tertiary = AlertRed,
    background = PitchBlack,
    surface = PitchBlack,
    onPrimary = PitchBlack,
    onSecondary = PureWhite,
    onTertiary = PureWhite,
    onBackground = PureWhite,
    onSurface = PureWhite,
    surfaceVariant = PitchBlack.copy(alpha = 0.03f),
    outline = GlassLine
)

private val LightColorScheme = lightColorScheme(
    primary = Color(0xFF156F2A),
    secondary = Color(0xFF1F2937),
    tertiary = Color(0xFFB42318),
    background = Color(0xFFF7F8FA),
    surface = Color(0xFFFFFFFF),
    onPrimary = Color(0xFFFFFFFF),
    onSecondary = Color(0xFF111827),
    onTertiary = Color(0xFFFFFFFF),
    onBackground = Color(0xFF111827),
    onSurface = Color(0xFF111827),
    surfaceVariant = Color(0xFFF1F5F9),
    outline = Color(0xFFD0D5DD)
)

@Composable
fun MyApplicationTheme(
    darkTheme: Boolean = true,
    content: @Composable () -> Unit
) {
    val view = LocalView.current
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            window.navigationBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}

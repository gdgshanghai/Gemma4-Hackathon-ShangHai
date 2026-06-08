package com.example.myapplication.utils

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

data class ResponsiveDimensions(
    val tiny: Dp = 4.dp,
    val small: Dp = 8.dp,
    val medium: Dp = 16.dp,
    val large: Dp = 24.dp,
    val extraLarge: Dp = 32.dp,
    val huge: Dp = 48.dp,
    val messageWidth: Float = 0.85f,
    val fontSizeTitle: Float = 24f,
    val fontSizeBody: Float = 17f,
    val fontSizeSmall: Float = 13f,
    val fontSizeLabel: Float = 11f,
    val cardRadius: Dp = 20.dp,
    val buttonRadius: Dp = 8.dp
)

enum class ScreenSize {
    COMPACT, MEDIUM, EXPANDED
}

@Composable
fun rememberResponsiveDimensions(): ResponsiveDimensions {
    val configuration = LocalConfiguration.current
    val density = LocalDensity.current
    
    val screenWidthDp = configuration.screenWidthDp.dp
    val screenHeightDp = configuration.screenHeightDp.dp
    val isPortrait = configuration.orientation == android.content.res.Configuration.ORIENTATION_PORTRAIT
    
    val screenSize = when {
        screenWidthDp < 360.dp -> ScreenSize.COMPACT
        screenWidthDp < 600.dp -> ScreenSize.MEDIUM
        else -> ScreenSize.EXPANDED
    }
    
    return remember(screenWidthDp, isPortrait) {
        when (screenSize) {
            ScreenSize.COMPACT -> ResponsiveDimensions(
                tiny = 2.dp,
                small = 6.dp,
                medium = 12.dp,
                large = 18.dp,
                extraLarge = 24.dp,
                huge = 36.dp,
                messageWidth = 0.9f,
                fontSizeTitle = 20f,
                fontSizeBody = 15f,
                fontSizeSmall = 12f,
                fontSizeLabel = 10f,
                cardRadius = 16.dp,
                buttonRadius = 6.dp
            )
            ScreenSize.MEDIUM -> ResponsiveDimensions(
                tiny = 4.dp,
                small = 8.dp,
                medium = 16.dp,
                large = 24.dp,
                extraLarge = 32.dp,
                huge = 48.dp,
                messageWidth = 0.85f,
                fontSizeTitle = 24f,
                fontSizeBody = 17f,
                fontSizeSmall = 13f,
                fontSizeLabel = 11f,
                cardRadius = 20.dp,
                buttonRadius = 8.dp
            )
            ScreenSize.EXPANDED -> ResponsiveDimensions(
                tiny = 6.dp,
                small = 12.dp,
                medium = 24.dp,
                large = 32.dp,
                extraLarge = 40.dp,
                huge = 64.dp,
                messageWidth = 0.7f,
                fontSizeTitle = 28f,
                fontSizeBody = 19f,
                fontSizeSmall = 15f,
                fontSizeLabel = 12f,
                cardRadius = 24.dp,
                buttonRadius = 10.dp
            )
        }
    }
}

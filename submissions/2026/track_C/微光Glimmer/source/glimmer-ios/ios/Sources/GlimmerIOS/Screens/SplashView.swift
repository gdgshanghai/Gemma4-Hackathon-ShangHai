import SwiftUI

/// 屏1 启动页 — Figma 66:468 「启动App」
///
/// 自适应布局：奶油底铺满；光束贴底部全宽；吉祥物 + 字标在垂直中部成组；
/// tagline 贴底（安全区内）。不依赖固定 375×812 画布。
struct SplashView: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var body: some View {
        ZStack {
            GTheme.splashBg.ignoresSafeArea()

            // 底部光束（66:470）—— 竖直翻转、全宽，作为字标背后的光晕
            VStack {
                Spacer()
                bundleImage("light_beam")
                    .resizable()
                    .scaledToFit()
                    .scaleEffect(y: -1)
                    .frame(maxWidth: .infinity)
            }
            .ignoresSafeArea()

            VStack(spacing: 8) {
                Spacer()

                // 毛绒星星吉祥物（66:473，旋转 -4.77°）
                bundleImage("star_splash")
                    .resizable().scaledToFit()
                    .frame(width: 202, height: 202)
                    .rotationEffect(.degrees(-4.77))

                // Glimmer 字标（66:474）
                bundleImage("glimmer_wordmark")
                    .resizable().scaledToFit()
                    .frame(width: 268)

                Spacer()

                // tagline（66:472）
                Text(L10n.text(.splashTagline, language: languageStore.language))
                    .font(.system(size: 14))
                    .tracking(0.2)
                    .foregroundStyle(GTheme.subtle)
                    .padding(.bottom, 40)
            }
        }
    }
}

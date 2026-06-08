import SwiftUI

/// 屏3 首页 — Figma 64:414 「进入App 页面」
///
/// 自适应布局：标题靠左、探头星星从右上探出；视频分析卡片撑满宽度；
/// 隐私文案 + 底部 Tab 自然落在安全区内。
struct HomeView: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var onStart: () -> Void = {}
    var onSelectReport: () -> Void = {}

    var body: some View {
        ZStack {
            Color(hex: 0xF2F2EC).ignoresSafeArea()

            VStack(spacing: 0) {
                header
                    .padding(.top, 44)

                videoCard
                    .padding(.top, 24)

                Text(L10n.text(.homePrivacy, language: languageStore.language))
                    .font(.system(size: 13))
                    .foregroundStyle(GTheme.subtle)
                    .padding(.top, 18)

                Spacer(minLength: 0)

                GlimmerTabBar(active: .analyze) { tab in
                    if tab == .report { onSelectReport() }
                }
            }
            .padding(.horizontal, 16)
        }
    }

    // MARK: - 头部（标题 + 探头星星）

    private var header: some View {
        ZStack(alignment: .topTrailing) {
            HStack {
                Text(L10n.text(.homeTitle, language: languageStore.language))
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundStyle(GTheme.ink)
                    .lineSpacing(6)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }
            .padding(.top, 18)

            // 右上角探头星星（64:415）—— 资源已是最终方向，不再叠变换；向右上探出
            bundleImage("star_peek")
                .resizable().scaledToFill()
                .frame(width: 168, height: 168)
                .offset(x: 28, y: -28)
        }
    }

    // MARK: - 视频分析卡片（64:444）

    private var videoCard: some View {
#if os(macOS)
        videoCardContent
            .frame(maxWidth: .infinity)
            .contentShape(RoundedRectangle(cornerRadius: 24))
            .onTapGesture(perform: onStart)
            .accessibilityAddTraits(.isButton)
#else
        Button(action: onStart) {
            videoCardContent
        }
        .frame(maxWidth: .infinity)
        .contentShape(RoundedRectangle(cornerRadius: 24))
        .buttonStyle(.plain)
#endif
    }

    private var videoCardContent: some View {
        VStack(spacing: 0) {
            // 上半浅蓝块 + 手机插画（64:452/453，旋转 12°）
            ZStack {
                Color(hex: 0xEEF2F5)
                bundleImage("phone_rec")
                    .resizable().scaledToFit()
                    .rotationEffect(.degrees(12))
                    .padding(20)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 300)
            .clipped()

            // 底部信息行（64:445）
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(L10n.text(.videoAnalysis, language: languageStore.language))
                        .font(.system(size: 20, weight: .medium))
                        .foregroundStyle(GTheme.ink)
                        .lineLimit(1)
                    Text(L10n.text(.videoAnalysisSubtitle, language: languageStore.language))
                        .font(.system(size: 13))
                        .foregroundStyle(GTheme.subtle)
                        .lineLimit(2)
                }
                Spacer(minLength: 0)
                // 64:450：竖直箭头旋 90° → 视觉向右指（播放感）
                Image(systemName: "arrow.up")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(GTheme.onInk)
                    .rotationEffect(.degrees(90))
                    .frame(width: 40, height: 40)
                    .background(GTheme.ink, in: Circle())
            }
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 20)
            .padding(.vertical, 22)
        }
        .frame(maxWidth: .infinity)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .contentShape(RoundedRectangle(cornerRadius: 24))
    }
}

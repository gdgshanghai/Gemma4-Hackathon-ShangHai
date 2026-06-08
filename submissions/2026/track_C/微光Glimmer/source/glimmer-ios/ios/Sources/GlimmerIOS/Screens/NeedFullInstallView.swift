import SwiftUI

/// macOS Lite 更新版在本机检测不到已播种模型时显示。
/// 不走下载兜底：让用户先装一次「完整安装包」（首发版会把模型一次性放好）。
struct NeedFullInstallView: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var body: some View {
        ZStack {
            GTheme.bg.ignoresSafeArea()

            VStack(spacing: 18) {
                Spacer(minLength: 0)

                bundleImage("glimmer_wordmark")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 214)

                Text(L10n.text(.needFullInstallTitle, language: languageStore.language))
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundStyle(GTheme.ink)
                    .padding(.top, 32)

                Text(L10n.text(.needFullInstallMessage, language: languageStore.language))
                    .font(.system(size: 13, weight: .regular))
                    .multilineTextAlignment(.center)
                    .foregroundStyle(GTheme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 4)

                Button {
                    #if os(macOS)
                    NSApplication.shared.terminate(nil)
                    #endif
                } label: {
                    Text(L10n.text(.quit, language: languageStore.language))
                        .font(.system(size: 15, weight: .medium))
                        .foregroundStyle(GTheme.onInk)
                        .frame(minWidth: 120, minHeight: 38)
                        .background(GTheme.ink, in: Capsule())
                }
                .buttonStyle(.plain)
                .padding(.top, 20)

                Spacer(minLength: 0)
            }
            .padding(.horizontal, 32)
        }
    }
}

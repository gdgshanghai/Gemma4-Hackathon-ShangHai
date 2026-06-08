import SwiftUI

/// 屏5 拍摄完成弹窗 — Figma 53:332 「拍摄完成」
/// 半透明遮罩 + 居中白卡 + 主按钮「视频分析」/ 文字按钮「取消」
struct CaptureDoneDialog: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var onConfirm: () -> Void = {}
    var onCancel: () -> Void = {}

    var body: some View {
        ZStack {
            // 50% 黑遮罩
            Color.black.opacity(0.5).ignoresSafeArea()
                .onTapGesture(perform: onCancel)

            // 白卡
            VStack(spacing: 24) {
                VStack(spacing: 8) {
                    Text(L10n.text(.captureDone, language: languageStore.language))
                        .font(.system(size: 17, weight: .medium))
                        .foregroundStyle(GTheme.ink)
                    Text(L10n.text(.captureDoneMessage, language: languageStore.language))
                        .font(.system(size: 15))
                        .foregroundStyle(GTheme.subtle)
                        .multilineTextAlignment(.center)
                        .lineSpacing(15 * 0.5)
                }

                VStack(spacing: 12) {
                    Button(action: onConfirm) {
                        Text(L10n.text(.startAnalysis, language: languageStore.language))
                            .font(.system(size: 15, weight: .medium))
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity)
                            .frame(height: 44)
                            .background(GTheme.ink, in: RoundedRectangle(cornerRadius: 12))
                    }
                    .buttonStyle(.plain)

                    Button(action: onCancel) {
                        Text(L10n.text(.cancel, language: languageStore.language))
                            .font(.system(size: 15, weight: .medium))
                            .foregroundStyle(GTheme.ink)
                            .frame(maxWidth: .infinity)
                            .frame(height: 22)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(24)
            .frame(width: 279)
            .background(.white, in: RoundedRectangle(cornerRadius: 24))
        }
    }
}

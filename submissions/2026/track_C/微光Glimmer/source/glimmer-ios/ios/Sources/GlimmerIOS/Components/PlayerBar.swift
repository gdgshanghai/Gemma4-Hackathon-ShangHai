import SwiftUI

/// 视频播放条 — Figma 53:480 / 53:802
/// 浅灰胶囊容器(#f6f6f5, 24 圆角)、左播放按钮、视频标题、右侧时长
struct PlayerBar: View {
    var title: String = "2026-06-03 12:12:12 视频"
    var duration: String = "02:05"
    var onPlay: () -> Void = {}

    var body: some View {
        HStack(spacing: 12) {
            Button(action: onPlay) {
                bundleImage("icon_play")
                    .resizable().scaledToFit()
                    .frame(width: 32, height: 32)
            }
            .buttonStyle(.plain)

            Text(title)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(GTheme.ink.opacity(0.8))
                .lineLimit(1)

            Spacer(minLength: 0)

            Text(duration)
                .font(.system(size: 14))
                .foregroundStyle(GTheme.ink.opacity(0.66))
        }
        .padding(.leading, 8)
        .padding(.trailing, 12)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, minHeight: 48)
        .background(Color(hex: 0xF6F6F5), in: RoundedRectangle(cornerRadius: 24))
    }
}

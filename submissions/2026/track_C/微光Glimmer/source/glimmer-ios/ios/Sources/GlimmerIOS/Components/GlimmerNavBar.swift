import SwiftUI

/// 顶部 Nav：返回胶囊按钮（左 16，size 40，圆 100，玻璃感）+ 居中标题（PingFang SC 14 / #29291F）
/// 用于：分析中(53:472)、报告结论(53:794)、追问对话(53:1000)
struct GlimmerNavBar: View {
    var title: String
    var onBack: () -> Void = {}

    var body: some View {
        ZStack {
            Text(title)
                .font(.system(size: 14))
                .foregroundStyle(GTheme.ink)
                .frame(maxWidth: .infinity)

            HStack {
                Button(action: onBack) {
                    bundleImage("icon_chevron_back")
                        .resizable().scaledToFit()
                        .frame(width: 16, height: 16)
                        .frame(width: 40, height: 40)
                        .background(Color(hex: 0xFAFAF7, alpha: 0.8), in: Circle())
                        .overlay(Circle().stroke(.white, lineWidth: 1))
                        .shadow(color: .black.opacity(0.06), radius: 12, y: 2)
                }
                .buttonStyle(.plain)
                Spacer()
            }
            .padding(.horizontal, 16)
        }
        .frame(maxWidth: .infinity, minHeight: 54)
    }
}

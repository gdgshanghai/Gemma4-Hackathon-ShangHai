import SwiftUI

enum GlimmerTab { case analyze, report }

/// 底部 Tab（分析 / 报告）— Figma 新版通用底栏（home/analyzing/report 复用）。
/// 仅渲染 tab 行（375×52，位于 Home Indicator 之上）。
struct GlimmerTabBar: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var active: GlimmerTab
    var onSelect: (GlimmerTab) -> Void = { _ in }

    var body: some View {
        HStack(spacing: 24) {
            item(icon: "tab_analyze", label: L10n.text(.analyzeTab, language: languageStore.language), tab: .analyze, on: active == .analyze)
            item(icon: "tab_report", label: L10n.text(.reportTab, language: languageStore.language), tab: .report, on: active == .report)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .frame(maxWidth: .infinity, minHeight: 52, alignment: .top)
    }

    private func item(icon: String, label: String, tab: GlimmerTab, on: Bool) -> some View {
        Button {
            onSelect(tab)
        } label: {
            VStack(spacing: 2) {
                bundleImage(icon)
                    .resizable().scaledToFit()
                    .frame(width: 28, height: 28)
                    .opacity(on ? 1 : 0.6)
                Text(label)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(on ? GTheme.ink : GTheme.subtle)
            }
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.plain)
    }
}

import SwiftUI

/// 可视化壳的公共入口：按环境变量 `GLIMMER_SCREEN` 深链到单屏（注入 mock 数据）。
/// 供 GlimmerGallery（仅模拟器）target 调用，专用于 visual loop 逐屏还原。
public struct GalleryRoot: View {
    @State private var languageStore = AppLanguageStore()

    public init() {}

    private var screen: String {
        // 没指定时跑完整流程，等同于线上 App 体验；
        // visual loop 时通过 GLIMMER_SCREEN=splash|loading|home|... 深链到单屏。
        ProcessInfo.processInfo.environment["GLIMMER_SCREEN"]?.lowercased() ?? "flow"
    }

    public var body: some View {
        content
            .environment(languageStore)
    }

    @ViewBuilder
    private var content: some View {
        switch screen {
        case "flow":         AppRootView()
        case "splash":       SplashView()
        case "loading":      ModelLoadingView()
        case "home":         HomeView()
        case "camera":       placeholder("camera 未实现")
        case "capture_done":
            ZStack {
                HomeView()
                CaptureDoneDialog()
            }
        case "source_sheet":
            // 让 home 一启动就触发 action sheet，用来截图验证样式
            SourceSheetDemo()
        case "analyzing":    AnalyzingDemoContainer()
        case "report":       placeholder("report 未实现")
        case "qa":           placeholder("qa 未实现")
        case "analyze":
            placeholder("Use the production app flow to choose a local video.")
        default:             placeholder("未知屏: \(screen)")
        }
    }

    private func placeholder(_ text: String) -> some View {
        ZStack {
            GTheme.bg.ignoresSafeArea()
            Text(text).font(.system(size: 16)).foregroundStyle(GTheme.subtle)
        }
    }
}

/// 启动即触发 action sheet 的 home，用来验证选择器样式。
private struct SourceSheetDemo: View {
    var body: some View {
        HomeView()
    }
}

import SwiftUI
import GlimmerIOS

/// macOS 原生宿主：复用 GlimmerIOS 包里的真实流程（GlimmerRootView）。
/// 模型在 Mac 上 Metal 原生运行，内存充足、无 iOS jetsam 限制。
@main
struct GlimmerMacApp: App {
    var body: some Scene {
        WindowGroup {
            GlimmerRootView()
                .frame(minWidth: 430, minHeight: 760)
        }
        .windowResizability(.contentSize)
    }
}

import SwiftUI
import GlimmerIOS

/// 仅模拟器用的可视化壳：按环境变量 GLIMMER_SCREEN 深链到任意单屏，
/// 注入 mock 数据，不加载 GGUF 模型，秒级构建，专供 visual loop 逐屏还原。
@main
struct GlimmerGalleryApp: App {
    var body: some Scene {
        WindowGroup {
            GalleryRoot()
        }
    }
}

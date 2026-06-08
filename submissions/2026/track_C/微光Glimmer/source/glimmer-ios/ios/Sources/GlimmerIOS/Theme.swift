import SwiftUI
#if canImport(UIKit)
import UIKit
#elseif canImport(AppKit)
import AppKit
#endif

extension Color {
    init(hex: UInt32, alpha: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: alpha
        )
    }
}

enum ASDTheme {
    static let bg = Color(hex: 0xFFFEFA)        // 奶油底
    static let card = Color(hex: 0xF1F1EF)      // 卡片灰
    static let ink = Color(hex: 0x000000)
    static let subtle = Color(hex: 0x1F2329, alpha: 0.6)  // 隐私说明
    static let brand = Color(hex: 0x0066FF)     // yomoa 品牌蓝
}

/// 从 bundle 加载图(loose PNG / 资源目录)。iOS 用 UIImage，macOS 用 NSImage。
func bundleImage(_ name: String) -> Image {
#if canImport(UIKit)
    if let ui = UIImage(named: name) { return Image(uiImage: ui) }
#elseif canImport(AppKit)
    if let ns = NSImage(named: name) { return Image(nsImage: ns) }
#endif
    return Image(systemName: "photo")
}

// MARK: - 新版设计 tokens（来自 Figma VP12dmteNhyEKeKmh4Hp3r 新版画板，get_design_context 精确值）

enum GTheme {
    // 背景
    static let splashBg = Color(hex: 0xEDE9DF)   // 启动/加载：暖奶油底 rgb(237,233,223)
    static let bg = Color(hex: 0xF6F4EF)         // 首页/报告：浅奶油底（逐屏精校）
    static let blueCard = Color(hex: 0xE7EEF3)   // 首页视频分析卡：浅蓝
    static let card = Color(hex: 0xF2F1EC)        // 通用浅卡片
    static let white = Color(hex: 0xFFFFFF)

    // 文字 / 墨色（深橄榄，非纯黑）rgb(41,41,31)
    static let ink = Color(hex: 0x29291F)
    static let inkSecondary = Color(hex: 0x29291F, alpha: 0.85)
    static let subtle = Color(hex: 0x29291F, alpha: 0.6)
    static let faint = Color(hex: 0x29291F, alpha: 0.4)

    // 强调
    static let onInk = Color(hex: 0xFFFFFF)
    static let homeIndicator = Color(hex: 0x29291F)

    // 圆角
    static let cardRadius: CGFloat = 24
    static let dialogRadius: CGFloat = 20
}

extension Font {
    /// 粗圆体标题（系统 rounded design）
    static func gRounded(_ size: CGFloat, _ weight: Font.Weight = .bold) -> Font {
        .system(size: size, weight: weight, design: .rounded)
    }
}

/// 直接拿平台原生图（用于需要 intrinsic 尺寸/背景填充的场景）
#if canImport(UIKit)
func bundleUIImage(_ name: String) -> UIImage? { UIImage(named: name) }
#elseif canImport(AppKit)
func bundleUIImage(_ name: String) -> NSImage? { NSImage(named: name) }
#endif

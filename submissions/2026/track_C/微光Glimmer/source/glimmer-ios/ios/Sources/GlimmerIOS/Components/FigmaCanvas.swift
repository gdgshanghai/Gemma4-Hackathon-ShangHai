import SwiftUI

/// Figma 新版画板统一 375×812 设计基准。
/// 用一个固定 375×812 的坐标空间承载绝对定位的子视图，居中铺在屏幕上，
/// 这样无论真机/模拟器宽度多少，绝对坐标都与 Figma 一致（配合 375 宽模拟器即为全屏精确）。
struct FigmaCanvas<Content: View>: View {
    static var W: CGFloat { 375 }
    static var H: CGFloat { 812 }

    let background: Color
    @ViewBuilder var content: () -> Content

    init(background: Color, @ViewBuilder content: @escaping () -> Content) {
        self.background = background
        self.content = content
    }

    var body: some View {
        ZStack {
            background.ignoresSafeArea()
            ZStack(alignment: .topLeading) {
                Color.clear
                content()
            }
            .frame(width: Self.W, height: Self.H, alignment: .topLeading)
            .clipped()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

extension View {
    /// 按 Figma 的 (x,y,w,h)（左上角原点）绝对放置。
    func figmaFrame(x: CGFloat, y: CGFloat, w: CGFloat, h: CGFloat,
                    align: Alignment = .topLeading) -> some View {
        self.frame(width: w, height: h, alignment: align)
            .position(x: x + w / 2, y: y + h / 2)
    }
}

import SwiftUI
#if canImport(UIKit)
import UIKit
#endif

/// 引用计数的「保持亮屏」闸门。
///
/// 模型下载、设备端推理这类耗时的前台任务期间，禁用系统自动锁屏；任务结束后恢复，
/// 避免一直亮屏耗电。用计数而非布尔，确保多个任务重叠（如下载与分析同屏）时，
/// 只有全部结束（计数归零）才放开锁屏，不会被先结束的一方提前恢复。
@MainActor
enum ScreenWakeLock {
    private static var count = 0

    static func acquire() {
        count += 1
        apply()
    }

    static func release() {
        count = max(0, count - 1)
        apply()
    }

#if canImport(UIKit)
    private static func apply() {
        UIApplication.shared.isIdleTimerDisabled = count > 0
    }
#else
    // macOS：用 ProcessInfo 活动断言禁止系统休眠（计数>0 时持有，归零时释放）。
    private static var activityToken: NSObjectProtocol?
    private static func apply() {
        if count > 0 {
            if activityToken == nil {
                activityToken = ProcessInfo.processInfo.beginActivity(
                    options: [.idleSystemSleepDisabled, .userInitiated],
                    reason: "Glimmer 本地下载/推理进行中"
                )
            }
        } else if let token = activityToken {
            ProcessInfo.processInfo.endActivity(token)
            activityToken = nil
        }
    }
#endif
}

private struct KeepScreenAwakeModifier: ViewModifier {
    let isActive: Bool

    func body(content: Content) -> some View {
        content
            .onAppear { if isActive { ScreenWakeLock.acquire() } }
            .onChange(of: isActive) { oldValue, newValue in
                if newValue {
                    ScreenWakeLock.acquire()
                } else if oldValue {
                    ScreenWakeLock.release()
                }
            }
            .onDisappear { if isActive { ScreenWakeLock.release() } }
    }
}

extension View {
    /// `isActive` 为真期间保持屏幕常亮（禁用自动锁屏），转为假或视图消失后自动恢复。
    func keepScreenAwake(_ isActive: Bool) -> some View {
        modifier(KeepScreenAwakeModifier(isActive: isActive))
    }
}

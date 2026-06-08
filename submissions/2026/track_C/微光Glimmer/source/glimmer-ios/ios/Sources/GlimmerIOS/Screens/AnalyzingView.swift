import SwiftUI
import GlimmerCore

/// 屏6 分析中 — Figma 53:445
///
/// The model emits a strict 9-bit internal code. The UI reveals the mapped
/// behavior names at a fixed pace, then appends the derived background row.
struct AnalyzingView: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var timestamp: String = "2026-06-03 12:12:12"
    var partialCode: String = ""
    var onBack: () -> Void = {}
    /// 动画 + 模型都跑完时调用一次 — 用于切到报告页。
    /// 模型完成由 outside 通过 `streamFinished=true` 通知。
    var streamFinished: Bool = false
    var onAnimationDone: () -> Void = {}

    /// UI 节奏控制：模型实际 token 速度可能很快（真机几百 ms 出完 9 位），
    /// 我们不让 UI 跟着模型走，固定 0.9s/项 揭示，这样用户能看清每条行为词。
    @State private var revealedCount: Int = 0
    /// 通过 onChange 同步 displayCode.count；.task 闭包没法直接读 prop，
    /// 因为 SwiftUI 把 prop 作为 struct 的值快照，闭包捕获的是初始值。
    @State private var targetCount: Int = 0
    private let revealInterval: Duration = .milliseconds(900)

    /// Expands the model output with the app-derived background bit.
    /// Until the model code is complete, keep the partial code unchanged.
    private var displayCode: String {
        guard partialCode.count >= 9 else { return partialCode }
        let nine = String(partialCode.prefix(9))
        let b10: Character = nine.contains("1") ? "0" : "1"
        return nine + String(b10)
    }

    /// 当前已揭示的行为词（按位顺序）。`observed=true` 用强调色，否则灰。
    private var revealedLines: [(name: String, observed: Bool)] {
        let names = AnalyzingView.featureNames(language: languageStore.language)
        let chars = Array(displayCode)
        let visible = min(revealedCount, chars.count, names.count)
        return (0..<visible).map { i in
            (names[i], chars[i] == "1")
        }
    }

    var body: some View {
        ZStack {
            Color(hex: 0xF2F2EC).ignoresSafeArea()

            VStack(spacing: 12) {
                GlimmerNavBar(title: L10n.analysisReportTitle(timestamp: timestamp, language: languageStore.language), onBack: onBack)
                    .padding(.top, 8)

                analysisCard
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                PlayerBar(title: L10n.videoTitle(timestamp: timestamp, language: languageStore.language))

                GlimmerTabBar(active: .report)
            }
            .padding(.horizontal, 16)
        }
    }

    private var analysisCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 4) {
                bundleImage("icon_ai_small")
                    .resizable().scaledToFit()
                    .frame(width: 16, height: 16)
                    .padding(.top, 1) // 文案折行时与第一行文字顶部对齐
                // 省略号拼进同一个 Text：折行时跟在最后一个字后面，不再吊在整段文字右侧
                TimelineView(.periodic(from: .now, by: 0.45)) { ctx in
                    let phase = Int(ctx.date.timeIntervalSinceReferenceDate / 0.45) % 4
                    Text(L10n.text(.analyzingMessage, language: languageStore.language))
                        + Text(String(repeating: ".", count: phase))
                }
                .font(.system(size: 14))
                .foregroundStyle(Color(hex: 0x6A685D))
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            // 流式行为词列表 — 自动滚动到最新一行，填满卡片剩余高度
            StreamingBehaviorList(lines: revealedLines)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .padding(.horizontal, 20)
        .padding(.top, 32)
        .padding(.bottom, 12)
        // 同步 displayCode.count → targetCount（onChange 是 prop → @State 的桥梁）
        .onChange(of: displayCode.count, initial: true) { _, newCount in
            targetCount = newCount
        }
        // 跳转条件：模型跑完 且（揭示完 10 项 ‖ 无合法码=出错，没有可揭示项）
        .onChange(of: revealedCount) { _, newCount in
            if streamFinished && newCount >= 10 { onAnimationDone() }
        }
        .onChange(of: streamFinished) { _, finished in
            guard finished else { return }
            if revealedCount >= 10 || displayCode.isEmpty { onAnimationDone() }
        }
        // 节奏推进：单个长时任务读 @State targetCount（不能直接读 prop，闭包捕获的是初始快照）
        .task {
            while !Task.isCancelled {
                if revealedCount < targetCount {
                    try? await Task.sleep(for: revealInterval)
                    if Task.isCancelled { break }
                    revealedCount = min(revealedCount + 1, targetCount)
                } else {
                    try? await Task.sleep(for: .milliseconds(80))
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color(hex: 0xF6F6F5), in: RoundedRectangle(cornerRadius: 24))
    }

    /// User-facing behavior names in internal bit order.
    static func featureNames(language: GlimmerLanguage) -> [String] {
        AsdBehaviorParser.labels.map { $0.name(language: language) }
    }
}

// MARK: - 流式行为列表（真滚动 + 上下渐变蒙版）

private struct StreamingBehaviorList: View {
    let lines: [(name: String, observed: Bool)]

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView(.vertical, showsIndicators: false) {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(Array(lines.enumerated()), id: \.offset) { idx, line in
                        Text(line.name)
                            .font(.system(size: 14, weight: line.observed ? .medium : .light))
                            .foregroundStyle(line.observed ? GTheme.ink : Color(hex: 0x6A685D))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .frame(height: 22)
                            .id(idx)
                            .transition(.asymmetric(
                                insertion: .opacity.combined(with: .move(edge: .bottom)),
                                removal: .opacity
                            ))
                    }
                    // 业界推荐的 bottom sentinel：滚动只锚到这一项，避免随内容长度反复重算
                    Color.clear
                        .frame(height: 1)
                        .id("__bottom__")
                }
                .padding(.horizontal, 20)
                .padding(.top, 12)
                .padding(.bottom, 32) // 给底部留缓冲，避开 mask 淡出区
                // 关键：把 transition 接到 count 变化上，没有这个 transition 不会播
                .animation(.easeOut(duration: 0.55), value: lines.count)
            }
            .scrollDisabled(true)
            .mask(
                LinearGradient(
                    stops: [
                        .init(color: .clear, location: 0),
                        .init(color: .black, location: 0.18),
                        .init(color: .black, location: 0.82),
                        .init(color: .clear, location: 1)
                    ],
                    startPoint: .top, endPoint: .bottom
                )
            )
            .onChange(of: lines.count) { _, newCount in
                guard newCount > 0 else { return }
                // interpolatingSpring 出来的缓动比 easeOut 自然，
                // mass 较高 + damping 中等 → 轻微"滑行"感而非急刹
                withAnimation(.interpolatingSpring(mass: 1.4, stiffness: 70, damping: 18)) {
                    proxy.scrollTo("__bottom__", anchor: .bottom)
                }
            }
        }
    }
}

// MARK: - Gallery demo

/// Gallery 预览容器：模拟真模型 — 9 位 code 一次性"很快"出完（200ms/位，
/// 接近 iPhone 17 Pro 上 Gemma3n 的实际 token 速率）。UI 自己按 900ms/项
/// 节奏揭示，所以这里 sleep 多短都不影响视觉。
struct AnalyzingDemoContainer: View {
    @Environment(AppLanguageStore.self) private var languageStore

    @State private var partial = ""
    @State private var streamDone = false
    @State private var showReport = false
    /// Gallery 无模型 → 用假 chat 数据演示报告页交互。
    @State private var demoMessages: [ExplanationChatMessage] = []
    @State private var demoResponding = false
    /// 假 9 位 code（mock：观察到几项关注行为）。
    private let demoCode = "101100010"

    /// 从 demoCode 模板化结论（直接复用真实解析器，与 AsdBehaviorReport.conclusionText 完全一致）。
    private var demoConclusion: String {
        AsdBehaviorParser.parse(demoCode)?.conclusionText(language: languageStore.language) ?? ""
    }

    var body: some View {
        ZStack {
            if showReport {
                ReportConversationView(
                    timestamp: "2026-06-03 12:12:12",
                    videoDuration: "00:23",
                    conclusion: demoConclusion,
                    messages: demoMessages,
                    isChatReady: true,
                    isResponding: demoResponding,
                    onSend: { text in demoReply(to: text) },
                    onBack: { showReport = false }
                )
            } else {
                AnalyzingView(
                    partialCode: partial,
                    streamFinished: streamDone,
                    onAnimationDone: { showReport = true }
                )
            }
        }
        .task(id: showReport) {
            guard !showReport else { return }
            partial = ""
            streamDone = false
            for ch in demoCode {
                try? await Task.sleep(for: .milliseconds(200))
                partial.append(ch)
            }
            streamDone = true
        }
    }

    /// Gallery 假回复：echo 用户问题后给一句固定演示回答。
    private func demoReply(to text: String) {
        demoMessages.append(ExplanationChatMessage(role: .user, text: text))
        demoResponding = true
        Task {
            try? await Task.sleep(for: .milliseconds(900))
            demoResponding = false
            demoMessages.append(ExplanationChatMessage(
                role: .assistant,
                text: languageStore.language == .zh
                    ? "视频里孩子反复把罐头叠高、排列，这类重复摆弄物品的动作是筛查里关注的线索之一。单段视频不一定很明显，建议结合更多日常场景观察。"
                    : "In the video, the child repeatedly stacks and lines up cans. This kind of repeated object arrangement is one of the observable cues in the screening result. A single clip may not be obvious enough, so it is better to compare with more daily situations."
            ))
        }
    }
}

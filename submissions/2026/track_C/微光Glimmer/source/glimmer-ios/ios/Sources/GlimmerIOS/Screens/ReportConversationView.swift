import SwiftUI
import AVKit

/// 屏7 报告结论 + 屏8 追问对话 — Figma 53:751 + 53:994。
///
/// 纯展示视图（dumb view）：
/// - 结论散文（来自 `report.conclusionText`，模板化、零幻觉）按 SSE 节奏逐字揭示。
/// - 对话区由外部 `messages` 驱动（chenghuzi 的本地解释对话）；初始为空，用户提问后出现。
/// - 输入框在 `isChatReady` 前禁用（模型正在把视频灌进 KV-cache）。
struct ReportConversationView: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var timestamp: String = "2026-06-03 12:12:12"
    var videoTitle: String = ""
    var videoURL: URL?
    var videoDuration: String = "00:00"
    var conclusion: String
    var messages: [ExplanationChatMessage] = []
    var nonAnimatedMessageIDs: Set<UUID> = []
    var animateInitialContent: Bool = true
    var isChatReady: Bool = false
    var isResponding: Bool = false
    /// 对话初始化失败的文案（自动重试用尽后才非空）；非空时输入栏显示「重试」而非转圈。
    var chatError: String? = nil
    var onSend: (String) -> Void = { _ in }
    var onRetryChat: () -> Void = {}
    var onBack: () -> Void = {}
    var onSelectTab: (GlimmerTab) -> Void = { _ in }

    // 结论 SSE 节流：30ms/字符
    @State private var revealedCount: Int = 0
    private let charInterval: Duration = .milliseconds(30)
    @State private var draft: String = ""
    @FocusState private var inputFocused: Bool

    // 追问回复也按 SSE 节奏逐字揭示（与结论一致），18ms/字符；
    // 只揭示「刚到达的那条」助手消息，更早的消息保持完整。
    @State private var chatStreamID: UUID?
    @State private var chatStreamCount: Int = 0
    @State private var knownMessageIDs: Set<UUID> = []
    @State private var previewVideo: VideoPreviewItem?
    private let chatCharInterval: Duration = .milliseconds(18)

    private func revealedChatText(for msg: ExplanationChatMessage) -> String {
        guard msg.id == chatStreamID else { return msg.text }
        return String(msg.text.prefix(min(chatStreamCount, msg.text.count)))
    }

    private var revealedConclusion: String {
        let chars = Array(conclusion)
        return String(chars.prefix(min(revealedCount, chars.count)))
    }

    private var canSend: Bool {
        isChatReady && !isResponding && !draft.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private var inputPlaceholder: String {
        if isChatReady { return L10n.text(.chatReadyPlaceholder, language: languageStore.language) }
        if chatError != nil { return L10n.text(.chatFailedPlaceholder, language: languageStore.language) }
        return L10n.text(.chatPreparingPlaceholder, language: languageStore.language)
    }

    private var displayVideoTitle: String {
        videoTitle.isEmpty ? L10n.defaultVideoTitle(languageStore.language) : videoTitle
    }

    private var nonAnimatedMessageToken: String {
        nonAnimatedMessageIDs
            .map(\.uuidString)
            .sorted()
            .joined(separator: ",")
    }

    var body: some View {
        ZStack {
            GTheme.bg.ignoresSafeArea()

            ScrollViewReader { proxy in
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 20) {
                        conclusionCard
                        PlayerBar(
                            title: "\(timestamp) \(displayVideoTitle)",
                            duration: videoDuration,
                            onPlay: {
                                guard let videoURL else { return }
                                previewVideo = VideoPreviewItem(url: videoURL)
                            }
                        )
                        ForEach(messages) { msg in
                            switch msg.role {
                            case .user:      userBubble(msg.text)
                            case .assistant: assistantText(revealedChatText(for: msg), isError: msg.isError)
                            }
                        }
                        if isResponding { typingIndicator }
                        Color.clear.frame(height: 220).id("__bottom__")
                    }
                    .padding(.top, 76)
                    .padding(.horizontal, 16)
                }
                .onChange(of: messages.count) { _, _ in scrollToBottom(proxy) }
                .onChange(of: isResponding) { _, _ in scrollToBottom(proxy) }
                // 逐字揭示时实时跟到底（不加动画，避免每 18ms 排队动画卡顿）
                .onChange(of: chatStreamCount) { _, _ in proxy.scrollTo("__bottom__", anchor: .bottom) }
                // 键盘弹起时滚到底，保证最新一条在输入框上方可见
                .onChange(of: inputFocused) { _, f in if f { scrollToBottom(proxy) } }
            }

            // 顶部 nav（带不透明背景，遮住下方滚动内容，避免叠字）
            VStack(spacing: 0) {
                GlimmerNavBar(title: L10n.analysisReportTitle(timestamp: timestamp, language: languageStore.language), onBack: onBack)
                    .padding(.top, 8)
                    .padding(.bottom, 6)
                    .background(GTheme.bg)
                Spacer()
            }

            // 底部输入 + 提示 + Tab
            // 不再 ignoresSafeArea(.keyboard)：键盘弹起时这组会被顶到键盘上方，
            // 输入框可见。聚焦时隐藏脚注 + Tab，只留输入框贴在键盘上方。
            VStack(spacing: 0) {
                Spacer()
                VStack(spacing: 4) {
                    chatInputBar
                        .padding(.horizontal, 16)
                    if !inputFocused {
                        Text(L10n.text(.localOnlyFootnote, language: languageStore.language))
                            .font(.system(size: 12, weight: .light))
                            .foregroundStyle(Color(hex: 0x666664))
                        GlimmerTabBar(active: .report, onSelect: onSelectTab)
                    }
                }
                .padding(.top, 12)
                // 不透明背景，遮住下方滚动内容（用户气泡），避免与输入框占位文案叠字
                //（与顶部 nav 同样的处理）。顶沿用一小段渐隐让滚动内容平滑淡出，而非硬切。
                .background(alignment: .top) {
                    VStack(spacing: 0) {
                        LinearGradient(
                            colors: [GTheme.bg.opacity(0), GTheme.bg],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                        .frame(height: 20)
                        GTheme.bg
                    }
                    .padding(.top, -20)
                    .allowsHitTesting(false)
                }
            }

            if let previewVideo {
                FullscreenVideoPreview(
                    url: previewVideo.url,
                    onClose: { self.previewVideo = nil }
                )
                .zIndex(10)
            }
        }
        .task(id: conclusion) {
            guard animateInitialContent else {
                revealedCount = conclusion.count
                return
            }
            revealedCount = 0
            let total = conclusion.count
            while revealedCount < total && !Task.isCancelled {
                try? await Task.sleep(for: charInterval)
                if Task.isCancelled { return }
                revealedCount = min(revealedCount + 1, total)
            }
        }
        .task(id: nonAnimatedMessageToken) {
            knownMessageIDs.formUnion(nonAnimatedMessageIDs)
        }
        // 追问回复逐字揭示：每当最新一条变为「助手非错误」消息就从头流式播放
        .task(id: messages.last?.id) {
            guard let last = messages.last, last.role == .assistant, !last.isError else { return }
            guard !nonAnimatedMessageIDs.contains(last.id), !knownMessageIDs.contains(last.id) else {
                knownMessageIDs.insert(last.id)
                return
            }
            knownMessageIDs.formUnion(messages.map(\.id))
            chatStreamID = last.id
            chatStreamCount = 0
            let total = last.text.count
            while chatStreamCount < total && !Task.isCancelled {
                try? await Task.sleep(for: chatCharInterval)
                if Task.isCancelled { return }
                chatStreamCount = min(chatStreamCount + 1, total)
            }
        }
    }

    private func scrollToBottom(_ proxy: ScrollViewProxy) {
        withAnimation(.easeOut(duration: 0.25)) {
            proxy.scrollTo("__bottom__", anchor: .bottom)
        }
    }

    // MARK: - 结论卡

    private var conclusionCard: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 12) {
                Text(L10n.text(.reportConclusion, language: languageStore.language))
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(GTheme.ink)
                    .tracking(0.2)

                Text(revealedConclusion)
                    .font(.system(size: 17, weight: .light))
                    .foregroundStyle(GTheme.ink)
                    .lineSpacing(17 * 0.6)
                    .tracking(0.17)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(.horizontal, 19)
            .padding(.top, 19)
            .padding(.bottom, 16)

            HStack {
                Spacer()
                Text(L10n.text(.reportFootnote, language: languageStore.language))
                    .font(.system(size: 12, weight: .light))
                    .foregroundStyle(Color(hex: 0x666664))
                    .tracking(0.12)
                Spacer()
            }
            .frame(height: 32)
            .background(Color(hex: 0xF2F1EC, alpha: 0.74))
        }
        .background(GTheme.white.opacity(0.66))
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .shadow(color: .black.opacity(0.035), radius: 8, x: 0, y: 3)
    }

    // MARK: - 气泡

    private func userBubble(_ text: String) -> some View {
        HStack {
            Spacer(minLength: 60)
            Text(text)
                .font(.system(size: 16, weight: .light))
                .lineSpacing(8)
                .foregroundStyle(GTheme.ink)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(Color(hex: 0x29291F, alpha: 0.05),
                            in: RoundedRectangle(cornerRadius: 24))
        }
    }

    private func assistantText(_ text: String, isError: Bool) -> some View {
        Text(text)
            .font(.system(size: 16, weight: .light))
            .foregroundStyle(isError ? Color(hex: 0xC0392B) : Color(hex: 0x1F2329))
            .lineSpacing(8)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var typingIndicator: some View {
        HStack(spacing: 0) {
            Text(L10n.text(.thinking, language: languageStore.language))
            AnimatedThinkingDots()
        }
        .font(.system(size: 16, weight: .light))
        .foregroundStyle(Color(hex: 0x666664))
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - 输入

    private var chatInputBar: some View {
        HStack(spacing: 8) {
            // 单行输入：回车即发送（onSubmit 仅对单行 TextField 触发；axis:.vertical 时回车=换行不触发）。
            // 始终可聚焦/输入；能否发送由 canSend 门控（模型对话就绪前不发）。
            TextField(inputPlaceholder, text: $draft)
                .font(.system(size: 16, weight: .light))
                .foregroundStyle(GTheme.ink)
                .tint(Color(hex: 0xF8C304))
                .focused($inputFocused)
                .submitLabel(.send)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .onSubmit(submit)

            if isChatReady {
                Button(action: submit) {
                    Image(systemName: "arrow.up")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(width: 32, height: 32)
                        .background(GTheme.ink, in: Circle())
                }
                .buttonStyle(.plain)
                .padding(.trailing, 8)
                .disabled(!canSend)
                .opacity(canSend ? 1.0 : 0.4)
            } else if chatError != nil {
                // 自动重试用尽仍失败 → 给可点的「重试」按钮，避免无限转圈。
                Button(action: onRetryChat) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(width: 32, height: 32)
                        .background(Color(hex: 0xC0392B), in: Circle())
                }
                .buttonStyle(.plain)
                .padding(.trailing, 8)
            } else {
                // 对话还在准备（把视频重新灌进本地模型的 KV-cache）→ 显示 loading 而非灰箭头，
                // 避免看起来像“发送坏了”。就绪后切回可点的发送按钮。
                ProgressView()
                    .controlSize(.regular)
                    .tint(Color(hex: 0x666664))
                    .frame(width: 32, height: 32)
                    .padding(.trailing, 8)
            }
        }
        .frame(minHeight: 48)
        .background(.white.opacity(0.6))
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .shadow(color: .black.opacity(0.04), radius: 3, x: 0, y: 2)
    }

    private func submit() {
        let trimmed = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, isChatReady, !isResponding else { return }
        onSend(trimmed)
        draft = ""
    }
}

/// 「正在思考…」循环点点点。
private struct AnimatedThinkingDots: View {
    var body: some View {
        TimelineView(.periodic(from: .now, by: 0.45)) { ctx in
            let phase = Int(ctx.date.timeIntervalSinceReferenceDate / 0.45) % 4
            Text(String(repeating: ".", count: phase)).monospacedDigit()
        }
    }
}

private struct VideoPreviewItem: Identifiable {
    let id = UUID()
    let url: URL
}

private struct FullscreenVideoPreview: View {
    let url: URL
    var onClose: () -> Void
    @State private var player: AVPlayer

    init(url: URL, onClose: @escaping () -> Void) {
        self.url = url
        self.onClose = onClose
        _player = State(initialValue: AVPlayer(url: url))
    }

    var body: some View {
        ZStack(alignment: .topLeading) {
            Color.black.ignoresSafeArea()

            VideoPlayer(player: player)
                .ignoresSafeArea()

            Button(action: onClose) {
                Image(systemName: "xmark")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 44, height: 44)
                    .background(.black.opacity(0.38), in: Circle())
            }
            .buttonStyle(.plain)
            .padding(.top, 18)
            .padding(.leading, 16)
        }
        .onAppear {
            player.play()
        }
        .onDisappear {
            player.pause()
        }
    }
}

#Preview {
    ReportConversationView(
        videoDuration: "00:23",
        conclusion: "本次片段中，注意到一些需要关注的行为表现，例如：物体排列、上肢刻板动作。这些内容仅描述片段中的可见线索，供后续观察参考。",
        messages: [
            ExplanationChatMessage(role: .user, text: "所以小朋友现在这种行为是有一定倾向性的么？"),
            ExplanationChatMessage(role: .assistant, text: "视频里孩子反复把罐头叠高、排列，这类重复摆弄物品的动作是筛查里关注的线索之一。不过单段视频不一定很明显，建议结合更多日常场景观察。")
        ],
        isChatReady: true
    )
    .environment(AppLanguageStore())
}

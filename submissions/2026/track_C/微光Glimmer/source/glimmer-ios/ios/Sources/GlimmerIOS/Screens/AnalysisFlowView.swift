import SwiftUI
import AVFoundation
import GlimmerCore

/// 视频选好后的分析流程：预处理 → 9 位 code 分类（真实推理）→ 报告 + 本地解释对话。
///
/// 推理用 chenghuzi 的 `ScreeningService`：
/// - `analyze` 出 9 位 code → `report`（结论模板化，零幻觉）
/// - `beginExplanationChat` 把视频帧/音频 + 结果喂进 KV-cache，开本地多轮对话
/// AnalyzingView 的逐项揭示动画是 UI 自走节奏（与模型 token 速度无关），
/// 等模型出 code（streamFinished）且动画跑完，再切报告页。
struct AnalysisFlowView: View {
    let videoURL: URL
    var reportStore: ReportConversationStore? = nil

    @Environment(AppLanguageStore.self) private var languageStore
    @Environment(\.dismiss) private var dismiss
    @State private var service = ScreeningService()
    @State private var started = false
    @State private var showReport = false
    @State private var chatPrefillRequested = false
    @State private var reportRecordID: UUID?
    @State private var reportLanguage: GlimmerLanguage?
    @State private var videoDuration: String = "00:00"
    /// 预处理产物留存，供报告页开启解释对话时复用。
    @State private var media: PreparedGgufMedia?

    private let timestamp: String = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return f.string(from: Date())
    }()

    /// 模型分类完成 = report 已解析出来（或出错文案已就绪）。
    private var streamFinished: Bool { service.report != nil || !service.output.isEmpty }

    private var activeReportLanguage: GlimmerLanguage {
        reportLanguage ?? languageStore.language
    }

    var body: some View {
        ZStack {
            if showReport {
                ReportConversationView(
                    timestamp: timestamp,
                    videoTitle: videoURL.lastPathComponent.isEmpty ? L10n.defaultVideoTitle(activeReportLanguage) : videoURL.lastPathComponent,
                    videoURL: videoURL,
                    videoDuration: videoDuration,
                    conclusion: service.report?.conclusionText(language: activeReportLanguage) ?? service.output,
                    messages: service.chatMessages,
                    isChatReady: service.isChatReady,
                    isResponding: service.isChatResponding,
                    chatError: service.chatError,
                    onSend: { text in Task { await service.sendChatMessage(text, language: activeReportLanguage) } },
                    onRetryChat: retryChat,
                    onBack: { dismiss() },
                    onSelectTab: { tab in
                        if tab == .analyze { dismiss() }
                    }
                )
            } else {
                AnalyzingView(
                    timestamp: timestamp,
                    partialCode: service.report?.labelCode ?? "",
                    onBack: { dismiss() },
                    streamFinished: streamFinished,
                    onAnimationDone: {
                        guard !showReport else { return }
                        persistReportIfNeeded()
                        showReport = true
                        chatPrefillRequested = true
                    }
                )
            }
        }
        .task {
            guard !started else { return }
            started = true
            await run()
        }
        .task(id: videoURL) {
            videoDuration = await Self.readDuration(videoURL)
        }
        .task(id: chatPrefillRequested) {
            guard chatPrefillRequested else { return }
            await startChat()
        }
        .keepScreenAwake(!showReport || service.isChatResponding)
        .onChange(of: service.chatMessages) { _, messages in
            guard let reportRecordID else { return }
            reportStore?.updateMessages(recordID: reportRecordID, messages: messages)
        }
        .onDisappear {
            Task {
                await service.shutdown(language: activeReportLanguage)
            }
        }
    }

    private func run() async {
        let language = languageStore.language
        reportLanguage = language
        let prepared = await VideoAudioPreprocessor.prepare(videoURL: videoURL)
        guard !Task.isCancelled else { return }
        media = prepared
        guard !prepared.frameURLs.isEmpty else {
            service.output = L10n.text(.noVideoFrames, language: language)
            return
        }
        do {
            try await service.analyze(
                frameURLs: prepared.frameURLs,
                audioURL: prepared.audioURL,
                instruction: ScreeningService.userInstruction,
                language: language
            )
            guard !Task.isCancelled else { return }
        } catch {
            guard !Task.isCancelled else { return }
            service.output = L10n.genericError(detail: error.localizedDescription, language: language)
        }
    }

    /// 进报告页后，把同一段媒体 + 筛查结果灌进模型，开启本地解释对话。
    /// 失败先自动重试 `maxChatAutoRetries` 次（兜瞬时失败，如临时内存压力）；
    /// 仍失败才落到 chatError，由 UI 显示「重试」按钮交给用户手动触发。
    private func startChat() async {
        guard let media, service.report != nil, !service.isChatReady else { return }
        let maxChatAutoRetries = 1
        var attempt = 0
        while true {
            do {
                try await service.beginExplanationChat(
                    frameURLs: media.frameURLs,
                    audioURL: media.audioURL
                )
                return
            } catch is CancellationError {
                return  // 视图消失/任务取消，不算失败、不重试
            } catch {
                guard attempt < maxChatAutoRetries, !Task.isCancelled else {
                    service.chatError = L10n.localChatInitFailure(detail: error.localizedDescription, language: activeReportLanguage)
                    return
                }
                attempt += 1
                try? await Task.sleep(for: .seconds(1))
                guard !Task.isCancelled else { return }
            }
        }
    }

    /// 用户点「重试」：清掉错误态，重新跑一次对话初始化（含自动重试）。
    private func retryChat() {
        guard !service.isChatReady else { return }
        service.chatError = nil
        Task { await startChat() }
    }

    private func persistReportIfNeeded() {
        guard reportRecordID == nil, let reportStore, let report = service.report, let media else { return }
        do {
            let record = try reportStore.createRecord(
                timestamp: timestamp,
                videoURL: videoURL,
                videoDuration: videoDuration,
                report: report,
                media: media,
                language: activeReportLanguage
            )
            reportRecordID = record.id
        } catch {
            #if DEBUG
            print("Failed to persist report: \(error.localizedDescription)")
            #endif
        }
    }

    /// 读视频文件真实时长（秒）→ "MM:SS"。读失败回退 "00:00"。
    private static func readDuration(_ url: URL) async -> String {
        let asset = AVURLAsset(url: url)
        do {
            let d = try await asset.load(.duration)
            let secs = max(0, Int(CMTimeGetSeconds(d).rounded()))
            return String(format: "%02d:%02d", secs / 60, secs % 60)
        } catch {
            return "00:00"
        }
    }
}

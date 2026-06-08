import SwiftUI

struct ReportHistoryDetailView: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var store: ReportConversationStore
    let recordID: UUID
    var onBack: () -> Void = {}
    var onSelectAnalyze: () -> Void = {}

    @State private var service = ScreeningService()
    @State private var startedRecordID: UUID?

    private var record: ReportConversationRecord? {
        store.record(id: recordID)
    }

    var body: some View {
        if let record, let report = record.report {
            let media = store.media(for: record)
            ReportConversationView(
                timestamp: record.timestamp,
                videoTitle: record.videoTitle,
                videoURL: media.videoURL,
                videoDuration: record.videoDuration,
                conclusion: record.conclusion,
                messages: service.chatMessages,
                nonAnimatedMessageIDs: Set(record.messages.map(\.id)),
                animateInitialContent: false,
                isChatReady: service.isChatReady,
                isResponding: service.isChatResponding,
                chatError: service.chatError,
                onSend: { text in
                    Task { await service.sendChatMessage(text, language: record.reportLanguage) }
                },
                onRetryChat: { retryChat(record: record) },
                onBack: onBack,
                onSelectTab: { tab in
                    if tab == .analyze { onSelectAnalyze() }
                }
            )
            .task(id: record.id) {
                guard startedRecordID != record.id else { return }
                startedRecordID = record.id
                service.restore(report: report, messages: record.messages, language: record.reportLanguage)
                await startChat(record: record)
            }
            .onChange(of: service.chatMessages) { _, messages in
                store.updateMessages(recordID: record.id, messages: messages)
            }
            .onDisappear {
                Task {
                    await service.shutdown(language: record.reportLanguage)
                }
            }
        } else {
            missingRecordView
        }
    }

    private var missingRecordView: some View {
        ZStack {
            GTheme.bg.ignoresSafeArea()
            VStack(spacing: 20) {
                GlimmerNavBar(title: L10n.text(.analysisReport, language: languageStore.language), onBack: onBack)
                    .padding(.top, 8)
                Spacer()
                Text(L10n.text(.missingReport, language: languageStore.language))
                    .font(.system(size: 17, weight: .medium))
                    .foregroundStyle(GTheme.ink)
                Spacer()
                GlimmerTabBar(active: .report) { tab in
                    if tab == .analyze { onSelectAnalyze() }
                }
            }
            .padding(.horizontal, 16)
        }
    }

    /// 失败先自动重试 1 次，仍失败落 chatError，由 UI 显示「重试」按钮。
    private func startChat(record: ReportConversationRecord) async {
        let media = store.media(for: record)
        guard !media.frameURLs.isEmpty else {
            service.chatError = L10n.text(.missingHistoryFrames, language: record.reportLanguage)
            return
        }
        let maxChatAutoRetries = 1
        var attempt = 0
        while true {
            do {
                try await service.beginExplanationChat(
                    frameURLs: media.frameURLs,
                    audioURL: media.audioURL,
                    initialMessages: record.messages
                )
                return
            } catch is CancellationError {
                return
            } catch {
                guard attempt < maxChatAutoRetries, !Task.isCancelled else {
                    service.chatError = L10n.localChatInitFailure(detail: error.localizedDescription, language: record.reportLanguage)
                    return
                }
                attempt += 1
                try? await Task.sleep(for: .seconds(1))
                guard !Task.isCancelled else { return }
            }
        }
    }

    /// 用户点「重试」：清错误态，重新初始化对话。
    private func retryChat(record: ReportConversationRecord) {
        guard !service.isChatReady else { return }
        service.chatError = nil
        Task { await startChat(record: record) }
    }
}

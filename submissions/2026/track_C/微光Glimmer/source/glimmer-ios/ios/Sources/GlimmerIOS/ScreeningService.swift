import Foundation
import GlimmerCore

@MainActor
@Observable
final class ScreeningService {
    var output: String = ""
    var isRunning: Bool = false
    var statusText: String = L10n.text(.notLoaded, language: .zh)
    var report: AsdBehaviorReport?
    var chatMessages: [ExplanationChatMessage] = []
    var isChatReady: Bool = false
    var isChatResponding: Bool = false
    var chatError: String?

    private let ownerID = UUID()
    private let runner = AsdGgufRunner.shared
    private var isClosed = false
    private var language: GlimmerLanguage = .zh

    func ensureLoaded(language: GlimmerLanguage) async throws {
        self.language = language
        isClosed = false
        statusText = L10n.text(.loadingModel, language: language)

        try await runner.load(modelFiles: ModelCatalog.resolvedModelFiles(), ownerID: ownerID)
        try Task.checkCancellation()
        statusText = L10n.text(.readyLocalVisionAudio, language: language)
    }

    static let userInstruction = AsdGgufPrompts.userInstruction

    func restore(report: AsdBehaviorReport, messages: [ExplanationChatMessage], language: GlimmerLanguage) {
        self.language = language
        self.report = report
        self.output = report.jsonString
        self.chatMessages = messages
        self.isChatReady = false
        self.isChatResponding = false
        self.chatError = nil
    }

    func analyze(frameURLs: [URL], audioURL: URL?, instruction: String, language: GlimmerLanguage) async throws {
        try await ensureLoaded(language: language)

        isRunning = true
        output = ""
        report = nil
        chatMessages = []
        isChatReady = false
        isChatResponding = false
        chatError = nil
        await runner.invalidateExplanationSession(ownerID: ownerID)
        defer { isRunning = false }

        let supportsAudio = await runner.supportsAudio(ownerID: ownerID)
        let request = AsdGgufRequestBuilder.build(
            frameURLs: frameURLs,
            audioURL: supportsAudio ? audioURL : nil,
            userPrompt: instruction
        )
        let code = try await runner.generate(
            systemPrompt: AsdGgufPrompts.system,
            request: request,
            ownerID: ownerID
        )
            .trimmingCharacters(in: .whitespacesAndNewlines)
        try Task.checkCancellation()
        guard !isClosed else { return }
        if let parsed = AsdBehaviorParser.parse(code) {
            report = parsed
            output = parsed.jsonString
        } else {
            output = code
        }
    }

    func beginExplanationChat(
        frameURLs: [URL],
        audioURL: URL?,
        initialMessages: [ExplanationChatMessage] = []
    ) async throws {
        guard let report else { return }
        try await ensureLoaded(language: language)

        statusText = L10n.text(.preparingLocalChat, language: language)
        isChatReady = false
        isChatResponding = false
        chatError = nil
        chatMessages = initialMessages

        await runner.invalidateExplanationSession(ownerID: ownerID)
        let supportsAudio = await runner.supportsAudio(ownerID: ownerID)
        let request = AsdGgufRequestBuilder.build(
            frameURLs: frameURLs,
            audioURL: supportsAudio ? audioURL : nil,
            userPrompt: AsdExplanationPrompts.userInstruction(language: language)
        )
        try await runner.beginExplanationSession(
            systemPrompt: AsdExplanationPrompts.system(language: language),
            request: request,
            assistantContext: assistantContext(report: report, previousMessages: initialMessages, language: language),
            ownerID: ownerID
        )
        try Task.checkCancellation()
        guard !isClosed else { return }
        isChatReady = true
        statusText = L10n.text(.readyLocalChat, language: language)
    }

    func sendChatMessage(_ text: String, language: GlimmerLanguage? = nil) async {
        let language = language ?? self.language
        self.language = language
        let question = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !question.isEmpty, isChatReady, !isChatResponding else { return }

        chatMessages.append(ExplanationChatMessage(role: .user, text: question))
        isChatResponding = true
        chatError = nil
        defer { isChatResponding = false }

        do {
            let answer = try await runner.sendExplanationMessage(question, ownerID: ownerID)
                .trimmingCharacters(in: .whitespacesAndNewlines)
            try Task.checkCancellation()
            guard !isClosed else { return }
            chatMessages.append(
                ExplanationChatMessage(
                    role: .assistant,
                    text: answer.isEmpty ? L10n.text(.emptyAssistantReply, language: language) : answer
                )
            )
        } catch {
            let message = L10n.chatErrorMessage(detail: error.localizedDescription, language: language)
            chatError = message
            chatMessages.append(ExplanationChatMessage(role: .assistant, text: message, isError: true))
        }
    }

    func shutdown(language: GlimmerLanguage? = nil) async {
        let language = language ?? self.language
        isClosed = true
        isRunning = false
        isChatReady = false
        isChatResponding = false
        await runner.shutdown(ownerID: ownerID)
        statusText = L10n.text(.notLoaded, language: language)
    }

    static func assembleJSON(fromCode raw: String) -> String? {
        AsdBehaviorParser.parse(raw)?.jsonString
    }

    private func assistantContext(
        report: AsdBehaviorReport,
        previousMessages: [ExplanationChatMessage],
        language: GlimmerLanguage
    ) -> String {
        let baseContext = AsdExplanationPrompts.assistantResultContext(report: report, language: language)
        let transcript = previousMessages
            .filter { !$0.isError }
            .map { message in
                let role = message.role == .user ? "User" : "Assistant"
                return "\(role): \(message.text)"
            }
            .joined(separator: "\n")

        guard !transcript.isEmpty else { return baseContext }
        return """
        \(baseContext)

        Previous conversation:
        \(transcript)
        """
    }
}

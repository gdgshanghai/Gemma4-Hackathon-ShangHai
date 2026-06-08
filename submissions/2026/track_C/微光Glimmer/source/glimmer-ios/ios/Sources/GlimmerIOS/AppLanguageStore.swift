import Foundation
import GlimmerCore
import Observation

@Observable
final class AppLanguageStore {
    private enum Constants {
        static let key = "GlimmerAppLanguage"
    }

    var language: GlimmerLanguage {
        didSet {
            userDefaults.set(language.rawValue, forKey: Constants.key)
        }
    }

    private let userDefaults: UserDefaults

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
        if let value = userDefaults.string(forKey: Constants.key),
           let language = GlimmerLanguage(rawValue: value) {
            self.language = language
        } else {
            self.language = Self.preferredSystemLanguage()
        }
    }

    func setLanguage(_ language: GlimmerLanguage) {
        self.language = language
    }

    private static func preferredSystemLanguage() -> GlimmerLanguage {
        let preferred = Locale.preferredLanguages.first?.lowercased() ?? ""
        if preferred.hasPrefix("zh") {
            return .zh
        }
        return .en
    }
}

enum L10n {
    static func regionTitle(_ region: ModelDownloadRegion, language: GlimmerLanguage) -> String {
        switch (region, language) {
        case (.china, .zh):
            return "国内"
        case (.global, .zh):
            return "国外"
        case (.china, .en):
            return "China"
        case (.global, .en):
            return "Global"
        }
    }

    static func analysisReportTitle(timestamp: String, language: GlimmerLanguage) -> String {
        switch language {
        case .zh:
            return "\(timestamp) 分析报告"
        case .en:
            return "\(timestamp) Analysis Report"
        }
    }

    static func videoTitle(timestamp: String, language: GlimmerLanguage) -> String {
        switch language {
        case .zh:
            return "\(timestamp) 视频"
        case .en:
            return "\(timestamp) Video"
        }
    }

    static func defaultVideoTitle(_ language: GlimmerLanguage) -> String {
        switch language {
        case .zh:
            return "视频"
        case .en:
            return "Video"
        }
    }

    static func downloadFailureMessage(reason: String, language: GlimmerLanguage) -> String {
        switch language {
        case .zh:
            return "下载未完成：\(reason)"
        case .en:
            return "Download did not complete: \(reason)"
        }
    }

    static func chatErrorMessage(detail: String, language: GlimmerLanguage) -> String {
        switch language {
        case .zh:
            return "对话出错：\(detail)"
        case .en:
            return "Chat error: \(detail)"
        }
    }

    static func localChatInitFailure(detail: String, language: GlimmerLanguage) -> String {
        switch language {
        case .zh:
            return "本地对话初始化失败：\(detail)"
        case .en:
            return "Local chat initialization failed: \(detail)"
        }
    }

    static func genericError(detail: String, language: GlimmerLanguage) -> String {
        switch language {
        case .zh:
            return "出错：\(detail)"
        case .en:
            return "Error: \(detail)"
        }
    }

    static func languageToggleTitle(_ language: GlimmerLanguage) -> String {
        switch language {
        case .zh:
            return "中"
        case .en:
            return "En"
        }
    }

    static func text(_ key: Key, language: GlimmerLanguage) -> String {
        switch (key, language) {
        case (.selectModelSource, .zh): return "选择模型来源"
        case (.selectModelSource, .en): return "Choose Model Source"
        case (.downloadModelSource, .zh): return "下载模型"
        case (.downloadModelSource, .en): return "Download Model"
        case (.loadLocalModelSource, .zh): return "选择本地模型"
        case (.loadLocalModelSource, .en): return "Choose Local Model"
        case (.selectLocalModelHint, .zh): return "请选择 model-Q4_K_M.gguf 和 mmproj-bf16.gguf"
        case (.selectLocalModelHint, .en): return "Choose model-Q4_K_M.gguf and mmproj-bf16.gguf"
        case (.importLocalModel, .zh): return "正在导入本地模型…"
        case (.importLocalModel, .en): return "Importing local model..."
        case (.selectModelDownloadRegion, .zh): return "选择模型下载区域"
        case (.selectModelDownloadRegion, .en): return "Select Model Download Region"
        case (.prepareBundledModel, .zh): return "首次启动，正在准备本地模型…"
        case (.prepareBundledModel, .en): return "Preparing local model for first launch..."
        case (.modelLoadingMessage, .zh): return "首次使用前，下载大模型权重中...\n下载完毕后无需联网，可离线使用"
        case (.modelLoadingMessage, .en): return "Downloading model weights before first use...\nAfter this completes, Glimmer works offline"
        case (.keepAppForeground, .zh): return "下载完成前请保持应用处于前台"
        case (.keepAppForeground, .en): return "Keep the app in the foreground until the download completes"
        case (.keepAppForegroundForPreparation, .zh): return "完成前请保持应用处于前台"
        case (.keepAppForegroundForPreparation, .en): return "Keep the app in the foreground until this completes"
        case (.unknownReason, .zh): return "未知原因"
        case (.unknownReason, .en): return "Unknown reason"
        case (.splashTagline, .zh): return "和“微光”一起关爱“星星的孩子”"
        case (.splashTagline, .en): return "Observe with care, locally and privately"
        case (.homeTitle, .zh): return "选择你要开始的\n分析方式"
        case (.homeTitle, .en): return "Choose how to start\nanalysis"
        case (.homePrivacy, .zh): return "放心录制分析均在本地，不会涉及隐私泄漏"
        case (.homePrivacy, .en): return "Recording and analysis stay on this device"
        case (.videoAnalysis, .zh): return "视频分析"
        case (.videoAnalysis, .en): return "Video Analysis"
        case (.videoAnalysisSubtitle, .zh): return "拍摄孩子的视频，通过本地模型进行分析"
        case (.videoAnalysisSubtitle, .en): return "Record or choose a child behavior video for local analysis"
        case (.chooseVideoSource, .zh): return "选择视频来源"
        case (.chooseVideoSource, .en): return "Choose Video Source"
        case (.recordVideo, .zh): return "拍摄视频"
        case (.recordVideo, .en): return "Record Video"
        case (.chooseFromLibrary, .zh): return "从相册选择"
        case (.chooseFromLibrary, .en): return "Choose from Library"
        case (.cancel, .zh): return "取消"
        case (.cancel, .en): return "Cancel"
        case (.captureDone, .zh): return "拍摄完成"
        case (.captureDone, .en): return "Recording Complete"
        case (.captureDoneMessage, .zh): return "确认视频拍摄完成，开始进行分析"
        case (.captureDoneMessage, .en): return "Confirm the recording and start analysis"
        case (.startAnalysis, .zh): return "开始分析"
        case (.startAnalysis, .en): return "Start Analysis"
        case (.analyzingMessage, .zh): return "分析需要一些时间，请勿离开当前页面，以免任务中断重来"
        case (.analyzingMessage, .en): return "Analysis may take a moment. Keep this page open to avoid restarting"
        case (.analysisReport, .zh): return "分析报告"
        case (.analysisReport, .en): return "Analysis Report"
        case (.reportConclusion, .zh): return "报告结论"
        case (.reportConclusion, .en): return "Report Conclusion"
        case (.reportFootnote, .zh): return "本结果仅作早期信号提示，请结合日常观察判断"
        case (.reportFootnote, .en): return "Use this as an early signal reference and consider daily observations"
        case (.localOnlyFootnote, .zh): return "分析与对话全程在设备本地完成"
        case (.localOnlyFootnote, .en): return "Analysis and chat run entirely on device"
        case (.chatReadyPlaceholder, .zh): return "可以和我聊聊"
        case (.chatReadyPlaceholder, .en): return "Ask me about this result"
        case (.chatFailedPlaceholder, .zh): return "对话初始化失败，点右侧重试"
        case (.chatFailedPlaceholder, .en): return "Chat setup failed. Tap retry"
        case (.chatPreparingPlaceholder, .zh): return "正在准备本地对话…"
        case (.chatPreparingPlaceholder, .en): return "Preparing local chat..."
        case (.thinking, .zh): return "正在思考"
        case (.thinking, .en): return "Thinking"
        case (.reports, .zh): return "报告"
        case (.reports, .en): return "Reports"
        case (.noReports, .zh): return "暂无分析报告"
        case (.noReports, .en): return "No Analysis Reports"
        case (.noReportsMessage, .zh): return "完成一次视频分析后，结果会显示在这里。"
        case (.noReportsMessage, .en): return "After a video analysis completes, the result will appear here."
        case (.delete, .zh): return "删除"
        case (.delete, .en): return "Delete"
        case (.missingReport, .zh): return "这份报告已不存在"
        case (.missingReport, .en): return "This report no longer exists"
        case (.analyzeTab, .zh): return "分析"
        case (.analyzeTab, .en): return "Analyze"
        case (.reportTab, .zh): return "报告"
        case (.reportTab, .en): return "Reports"
        case (.notLoaded, .zh): return "未加载"
        case (.notLoaded, .en): return "Not loaded"
        case (.loadingModel, .zh): return "加载模型中…"
        case (.loadingModel, .en): return "Loading model..."
        case (.readyLocalVisionAudio, .zh): return "已就绪（本地 · 看 + 听）"
        case (.readyLocalVisionAudio, .en): return "Ready (local · vision + audio)"
        case (.preparingLocalChat, .zh): return "准备本地对话…"
        case (.preparingLocalChat, .en): return "Preparing local chat..."
        case (.readyLocalChat, .zh): return "已就绪（本地 · 可对话）"
        case (.readyLocalChat, .en): return "Ready (local · chat enabled)"
        case (.emptyAssistantReply, .zh): return "我暂时没有生成有效回答，请换个问法再试一次。"
        case (.emptyAssistantReply, .en): return "I did not generate a useful answer. Please try asking another way."
        case (.noVideoFrames, .zh): return "无法从视频中提取画面，请换一段视频重试。"
        case (.noVideoFrames, .en): return "Could not extract video frames. Please try another video."
        case (.missingHistoryFrames, .zh): return "原始视频画面已不可用，无法重建本地对话。"
        case (.missingHistoryFrames, .en): return "The original video frames are unavailable, so local chat cannot be rebuilt."
        case (.needFullInstallTitle, .zh): return "需要先安装完整版"
        case (.needFullInstallTitle, .en): return "Full Version Required"
        case (.needFullInstallMessage, .zh): return "当前是更新包（不含模型权重）。\n请先安装一次完整安装包（约 6 GB），\n模型会自动放好；之后再装本更新版即可立即使用。"
        case (.needFullInstallMessage, .en): return "This update package does not include model weights.\nInstall the full package once first (about 6 GB).\nThe model will be placed automatically; later updates can start immediately."
        case (.quit, .zh): return "退出"
        case (.quit, .en): return "Quit"
        }
    }

    enum Key {
        case selectModelSource
        case downloadModelSource
        case loadLocalModelSource
        case selectLocalModelHint
        case importLocalModel
        case selectModelDownloadRegion
        case prepareBundledModel
        case modelLoadingMessage
        case keepAppForeground
        case keepAppForegroundForPreparation
        case unknownReason
        case splashTagline
        case homeTitle
        case homePrivacy
        case videoAnalysis
        case videoAnalysisSubtitle
        case chooseVideoSource
        case recordVideo
        case chooseFromLibrary
        case cancel
        case captureDone
        case captureDoneMessage
        case startAnalysis
        case analyzingMessage
        case analysisReport
        case reportConclusion
        case reportFootnote
        case localOnlyFootnote
        case chatReadyPlaceholder
        case chatFailedPlaceholder
        case chatPreparingPlaceholder
        case thinking
        case reports
        case noReports
        case noReportsMessage
        case delete
        case missingReport
        case analyzeTab
        case reportTab
        case notLoaded
        case loadingModel
        case readyLocalVisionAudio
        case preparingLocalChat
        case readyLocalChat
        case emptyAssistantReply
        case noVideoFrames
        case missingHistoryFrames
        case needFullInstallTitle
        case needFullInstallMessage
        case quit
    }
}

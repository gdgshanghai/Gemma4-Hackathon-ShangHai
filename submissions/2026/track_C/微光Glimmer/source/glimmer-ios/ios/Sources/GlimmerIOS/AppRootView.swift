import SwiftUI
import OSLog
import UniformTypeIdentifiers
#if canImport(UIKit)
import UIKit
#endif
#if canImport(AppKit)
import AppKit
#endif

/// App flow coordinator: splash → model download gate → main flow.
public struct AppRootView: View {
    public init() {}

    private static let logger = Logger(subsystem: "cn.enactflow.glimmer", category: "ModelDownload")
#if os(macOS)
    private static let ggufContentType = UTType(filenameExtension: "gguf") ?? .data
#endif

    @Environment(AppLanguageStore.self) private var languageStore

    private enum Phase {
        case splash
        case selectRegion
#if os(macOS)
        case selectModelSource
#endif
        case loading
        case main
    }

    @State private var phase: Phase = .splash
    @State private var downloader = ModelDownloadManager()
    @State private var regionSelectionMessage: String?
    // macOS：把自带模型从 bundle 播种到 Application Support 时的进度/标记
    @State private var preparingFromBundle = false
    @State private var prepareProgress: CGFloat = 0
#if os(macOS)
    @State private var sourceSelectionMessage: String?
    @State private var importingLocalModels = false
    @State private var showLocalModelImporter = false
#endif

    private var preparingLocalModels: Bool {
#if os(macOS)
        preparingFromBundle || importingLocalModels
#else
        preparingFromBundle
#endif
    }

    private var loadingTitle: String? {
#if os(macOS)
        if preparingFromBundle {
            return L10n.text(.prepareBundledModel, language: languageStore.language)
        }
        if importingLocalModels {
            return L10n.text(.importLocalModel, language: languageStore.language)
        }
#endif
        return nil
    }

    private var loadingNotice: String? {
#if os(macOS)
        if preparingLocalModels {
            return L10n.text(.keepAppForegroundForPreparation, language: languageStore.language)
        }
#endif
        return nil
    }

    public var body: some View {
        ZStack {
            switch phase {
            case .splash:
                SplashView()
                    .transition(.opacity)
            case .selectRegion:
                ModelDownloadRegionSelectionView(
                    message: regionSelectionMessage,
                    onSelect: beginDownload
                )
                .transition(.opacity)
#if os(macOS)
            case .selectModelSource:
                MacModelSourceSelectionView(
                    message: sourceSelectionMessage,
                    onDownload: {
                        sourceSelectionMessage = nil
                        regionSelectionMessage = nil
                        phase = .selectRegion
                    },
                    onSelectLocalFiles: {
                        sourceSelectionMessage = nil
                        showLocalModelImporter = true
                    }
                )
                .transition(.opacity)
#endif
            case .loading:
                ModelLoadingView(
                    progress: preparingLocalModels ? prepareProgress : downloader.progress,
                    downloadedBytes: preparingLocalModels ? 0 : downloader.downloadedBytes,
                    totalBytes: preparingLocalModels ? 0 : downloader.totalBytes,
                    title: loadingTitle,
                    notice: loadingNotice
                )
                .transition(.opacity)
            case .main:
                MainFlow()
                    .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.4), value: phase)
        .keepScreenAwake(phase == .loading)
        .task {
            try? await Task.sleep(for: .seconds(1.6))

#if os(macOS)
            if downloader.hasTrustedModels {
                phase = .main
                return
            }

            if ModelCatalog.hasBundledModels && !downloader.hasTrustedModels {
                preparingFromBundle = true
                prepareProgress = 0
                phase = .loading
                await seedBundledModels()
                preparingFromBundle = false

                if downloader.hasTrustedModels {
                    phase = .main
                } else {
                    sourceSelectionMessage = L10n.text(.unknownReason, language: languageStore.language)
                    phase = .selectModelSource
                }
                return
            }

            sourceSelectionMessage = nil
            phase = .selectModelSource
            return
#else
            if downloader.hasTrustedModels {
                phase = .main
                return
            }

            guard let region = ModelDownloadRegionPreference.savedRegion() else {
                regionSelectionMessage = nil
                phase = .selectRegion
                return
            }

            beginDownload(region)
#endif
        }
#if os(macOS)
        .fileImporter(
            isPresented: $showLocalModelImporter,
            allowedContentTypes: [Self.ggufContentType],
            allowsMultipleSelection: true,
            onCompletion: handleLocalModelImport
        )
#endif
    }

    private func beginDownload(_ region: ModelDownloadRegion) {
        ModelDownloadRegionPreference.save(region)
        regionSelectionMessage = nil
        phase = .loading

        Task { @MainActor in
            await downloader.start(region: region)
            if downloader.isReady {
                phase = .main
            } else {
                ModelDownloadRegionPreference.clear()
                // 把真实失败原因透出来（之前只显示笼统文案，下载错误被吞掉，无法定位）
                let reason: String
                if case .failed(let detail) = downloader.phase {
                    reason = detail
                } else {
                    reason = L10n.text(.unknownReason, language: languageStore.language)
                }
                Self.logger.error("model download failed [\(region.rawValue, privacy: .public)]: \(reason, privacy: .public)")
                regionSelectionMessage = L10n.downloadFailureMessage(reason: reason, language: languageStore.language)
                phase = .selectRegion
            }
        }
    }

#if os(macOS)
    private func seedBundledModels() async {
        await Task.detached(priority: .userInitiated) {
            try? ModelCatalog.seedBundledModelsIfNeeded { p in
                Task { @MainActor in prepareProgress = CGFloat(p) }
            }
        }.value
    }

    private func handleLocalModelImport(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            do {
                let files = try ModelCatalog.localModelFiles(from: urls)
                importLocalModelFiles(files)
            } catch {
                sourceSelectionMessage = error.localizedDescription
                phase = .selectModelSource
            }
        case .failure(let error):
            if isFileImporterCancellation(error) {
                return
            }
            sourceSelectionMessage = error.localizedDescription
            phase = .selectModelSource
        }
    }

    private func importLocalModelFiles(_ files: AsdGgufModelFiles) {
        let modelURL = files.modelURL
        let mmprojURL = files.mmprojURL
        importingLocalModels = true
        prepareProgress = 0
        phase = .loading

        Task { @MainActor in
            do {
                try await Task.detached(priority: .userInitiated) {
                    try ModelCatalog.installLocalModelFiles(
                        modelURL: modelURL,
                        mmprojURL: mmprojURL
                    ) { p in
                        Task { @MainActor in prepareProgress = CGFloat(p) }
                    }
                }.value
                importingLocalModels = false
                if downloader.hasTrustedModels {
                    phase = .main
                } else {
                    sourceSelectionMessage = L10n.text(.unknownReason, language: languageStore.language)
                    phase = .selectModelSource
                }
            } catch {
                importingLocalModels = false
                Self.logger.error("local model import failed: \(error.localizedDescription, privacy: .public)")
                sourceSelectionMessage = error.localizedDescription
                phase = .selectModelSource
            }
        }
    }

    private func isFileImporterCancellation(_ error: Error) -> Bool {
        let nsError = error as NSError
        return nsError.domain == NSCocoaErrorDomain && nsError.code == CocoaError.Code.userCancelled.rawValue
    }
#endif
}

struct IdentifiableURL: Identifiable {
    let url: URL
    var id: String { url.absoluteString }
}

/// 主界面的流程：HomeView →（点卡片）系统来源选择器(拍摄/相册) → 拍完确认弹窗 → AnalyzingView → ReportView
struct MainFlow: View {
    @Environment(AppLanguageStore.self) private var languageStore

    @State private var activeTab: GlimmerTab = .analyze
    @State private var selectedReportID: UUID?
    @State private var reportStore = ReportConversationStore()
    @State private var showSourceSheet = false
    @State private var showLibrary = false
    @State private var showCamera = false
    /// 视频选好后挂起，等用户确认弹窗才进分析
    @State private var pendingURL: URL?
    @State private var analysisURL: IdentifiableURL?

#if os(iOS)
    private var cameraAvailable: Bool {
        UIImagePickerController.isSourceTypeAvailable(.camera)
    }
#endif

#if os(macOS)
    private static func importPickedVideo(_ url: URL) -> URL? {
        let needsStop = url.startAccessingSecurityScopedResource()
        defer { if needsStop { url.stopAccessingSecurityScopedResource() } }
        let ext = url.pathExtension.isEmpty ? "mov" : url.pathExtension
        let dest = FileManager.default.temporaryDirectory
            .appendingPathComponent("picked-\(UUID().uuidString).\(ext)")
        do {
            try? FileManager.default.removeItem(at: dest)
            try FileManager.default.copyItem(at: url, to: dest)
            return dest
        } catch {
            return nil
        }
    }

    @MainActor
    private func selectVideoOnMac() {
        let panel = NSOpenPanel()
        panel.title = L10n.text(.chooseFromLibrary, language: languageStore.language)
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.movie, .video]
        panel.begin { response in
            guard response == .OK,
                  let picked = panel.url,
                  let local = Self.importPickedVideo(picked) else { return }
            Task { @MainActor in
                analysisURL = IdentifiableURL(url: local)
            }
        }
    }
#endif

    var body: some View {
        ZStack {
            switch activeTab {
            case .analyze:
                HomeView(
                    onStart: {
#if os(iOS)
                        showSourceSheet = true
#else
                        selectVideoOnMac()
#endif
                    },
                    onSelectReport: { activeTab = .report }
                )
            case .report:
                if let selectedReportID, reportStore.record(id: selectedReportID) != nil {
                    ReportHistoryDetailView(
                        store: reportStore,
                        recordID: selectedReportID,
                        onBack: { self.selectedReportID = nil },
                        onSelectAnalyze: {
                            self.selectedReportID = nil
                            activeTab = .analyze
                        }
                    )
                } else {
                    ReportListView(
                        store: reportStore,
                        onOpen: { record in selectedReportID = record.id },
                        onSelectAnalyze: { activeTab = .analyze }
                    )
                }
            }

            if pendingURL != nil {
                CaptureDoneDialog(
                    onConfirm: {
                        if let url = pendingURL {
                            analysisURL = IdentifiableURL(url: url)
                        }
                        pendingURL = nil
                    },
                    onCancel: { pendingURL = nil }
                )
                .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.2), value: pendingURL)
        .task {
            reportStore.load()
        }
#if os(iOS)
        .confirmationDialog(L10n.text(.chooseVideoSource, language: languageStore.language), isPresented: $showSourceSheet, titleVisibility: .hidden) {
            if cameraAvailable {
                Button(L10n.text(.recordVideo, language: languageStore.language)) {
                    // 等 sheet 完全消失再弹 cover，避免 UIKit modal 冲突
                    Task {
                        try? await Task.sleep(for: .milliseconds(350))
                        showCamera = true
                    }
                }
            }
            Button(L10n.text(.chooseFromLibrary, language: languageStore.language)) {
                Task {
                    try? await Task.sleep(for: .milliseconds(350))
                    showLibrary = true
                }
            }
            Button(L10n.text(.cancel, language: languageStore.language), role: .cancel) {}
        }
        .fullScreenCover(isPresented: $showLibrary) {
            VideoPicker { url in
                showLibrary = false
                guard let url else { return }
                // 从相册选的视频直接进分析，不弹"拍摄完成"
                Task {
                    try? await Task.sleep(for: .milliseconds(450))
                    analysisURL = IdentifiableURL(url: url)
                }
            }
            .ignoresSafeArea()
        }
        .fullScreenCover(isPresented: $showCamera) {
            CameraVideoPicker { url in
                showCamera = false
                guard let url else { return }
                // 拍完才走"拍摄完成"确认弹窗
                Task {
                    try? await Task.sleep(for: .milliseconds(450))
                    pendingURL = url
                }
            }
            .ignoresSafeArea()
        }
        .fullScreenCover(item: $analysisURL) { item in
            AnalysisFlowView(videoURL: item.url, reportStore: reportStore)
        }
#else
        .sheet(item: $analysisURL) { item in
            AnalysisFlowView(videoURL: item.url, reportStore: reportStore)
                .frame(minWidth: 430, minHeight: 760)
        }
#endif
    }
}

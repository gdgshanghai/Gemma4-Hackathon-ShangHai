import Foundation

enum PreprocessParityRunner {
    private static var didStart = false
    private static let environment = ProcessInfo.processInfo.environment

    static func runIfConfigured() async {
        guard !didStart else { return }
        guard let videoRootValue = environment["GLIMMER_PREPROCESS_PARITY_VIDEO_ROOT"],
              !videoRootValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        didStart = true

        let outputValue = environment["GLIMMER_PREPROCESS_PARITY_OUTPUT"] ?? "Documents/preprocess_parity_results.json"
        let mediaOutputRootValue = environment["GLIMMER_PREPROCESS_PARITY_MEDIA_OUTPUT_ROOT"]
        let videoRoot = resolveContainerURL(videoRootValue)
        let outputURL = resolveContainerURL(outputValue)
        let mediaOutputRootURL = mediaOutputRootValue
            .flatMap { value -> URL? in
                let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !trimmed.isEmpty else { return nil }
                return resolveContainerURL(trimmed)
            }

        do {
            let records = try await run(videoRoot: videoRoot, mediaOutputRoot: mediaOutputRootURL)
            try write(records: records, outputURL: outputURL)
            print("GLIMMER_PREPROCESS_PARITY_RESULTS \(outputURL.path)")
        } catch {
            let failure = PreprocessParityRecord(
                sampleIndex: nil,
                sampleID: "__failure__",
                videoPath: videoRoot.path,
                mediaDirectoryPath: nil,
                frameCount: 0,
                audioPath: nil,
                diagnostics: nil,
                error: String(describing: error)
            )
            try? write(records: [failure], outputURL: outputURL)
            print("GLIMMER_PREPROCESS_PARITY_FAILURE \(String(describing: error))")
        }
    }

    private static func run(videoRoot: URL, mediaOutputRoot: URL?) async throws -> [PreprocessParityRecord] {
        let videos = try videoURLs(in: videoRoot)
        guard !videos.isEmpty else {
            throw PreprocessParityError.missingVideos(videoRoot.path)
        }
        if let mediaOutputRoot {
            try FileManager.default.createDirectory(at: mediaOutputRoot, withIntermediateDirectories: true)
        }

        var records: [PreprocessParityRecord] = []
        for (sampleIndex, videoURL) in videos.enumerated() {
            let prepared = await VideoAudioPreprocessor.prepare(videoURL: videoURL)
            let sampleID = videoURL.deletingPathExtension().lastPathComponent
            let stableMedia = try copyPreparedMediaIfNeeded(
                prepared: prepared,
                sampleID: sampleID,
                mediaOutputRoot: mediaOutputRoot
            )
            records.append(
                PreprocessParityRecord(
                    sampleIndex: sampleIndex,
                    sampleID: sampleID,
                    videoPath: videoURL.path,
                    mediaDirectoryPath: stableMedia.directory?.path,
                    frameCount: stableMedia.frameURLs.count,
                    audioPath: stableMedia.audioURL?.path,
                    diagnostics: prepared.diagnostics,
                    error: nil
                )
            )
        }
        return records
    }

    private static func videoURLs(in root: URL) throws -> [URL] {
        let fileManager = FileManager.default
        var isDirectory: ObjCBool = false
        guard fileManager.fileExists(atPath: root.path, isDirectory: &isDirectory) else {
            throw PreprocessParityError.missingVideoRoot(root.path)
        }
        if !isDirectory.boolValue {
            return isVideoFile(root) ? [root] : []
        }

        guard let enumerator = fileManager.enumerator(
            at: root,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ) else {
            throw PreprocessParityError.missingVideoRoot(root.path)
        }

        var urls: [URL] = []
        for case let url as URL in enumerator where isVideoFile(url) {
            urls.append(url)
        }
        return urls.sorted { $0.path < $1.path }
    }

    private static func copyPreparedMediaIfNeeded(
        prepared: PreparedGgufMedia,
        sampleID: String,
        mediaOutputRoot: URL?
    ) throws -> (directory: URL?, frameURLs: [URL], audioURL: URL?) {
        guard let mediaOutputRoot else {
            return (nil, prepared.frameURLs, prepared.audioURL)
        }

        let sampleDirectory = mediaOutputRoot.appendingPathComponent(sampleID, isDirectory: true)
        let fileManager = FileManager.default
        try? fileManager.removeItem(at: sampleDirectory)
        try fileManager.createDirectory(at: sampleDirectory, withIntermediateDirectories: true)

        let copiedFrameURLs = try prepared.frameURLs
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
            .enumerated()
            .map { index, sourceURL in
                let destinationURL = sampleDirectory.appendingPathComponent(String(format: "frame_%04d.jpg", index))
                try fileManager.copyItem(at: sourceURL, to: destinationURL)
                return destinationURL
            }

        let copiedAudioURL: URL?
        if let audioURL = prepared.audioURL {
            let destinationURL = sampleDirectory.appendingPathComponent("audio_16k_mono.wav")
            try fileManager.copyItem(at: audioURL, to: destinationURL)
            copiedAudioURL = destinationURL
        } else {
            copiedAudioURL = nil
        }

        return (sampleDirectory, copiedFrameURLs, copiedAudioURL)
    }

    private static func isVideoFile(_ url: URL) -> Bool {
        switch url.pathExtension.lowercased() {
        case "mp4", "mov", "m4v":
            return true
        default:
            return false
        }
    }

    private static func resolveContainerURL(_ value: String) -> URL {
        if value.hasPrefix("/") {
            return URL(fileURLWithPath: value)
        }
        return URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(value)
    }

    private static func write(records: [PreprocessParityRecord], outputURL: URL) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(
            PreprocessParityResult(
                generatedAt: ISO8601DateFormatter().string(from: Date()),
                records: records
            )
        )
        try FileManager.default.createDirectory(
            at: outputURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try data.write(to: outputURL, options: [.atomic])
    }
}

private struct PreprocessParityResult: Codable {
    let generatedAt: String
    let records: [PreprocessParityRecord]
}

private struct PreprocessParityRecord: Codable {
    let sampleIndex: Int?
    let sampleID: String
    let videoPath: String
    let mediaDirectoryPath: String?
    let frameCount: Int
    let audioPath: String?
    let diagnostics: GgufMediaDiagnostics?
    let error: String?
}

private enum PreprocessParityError: LocalizedError {
    case missingVideoRoot(String)
    case missingVideos(String)

    var errorDescription: String? {
        switch self {
        case .missingVideoRoot(let path):
            return "Missing preprocess parity video root: \(path)"
        case .missingVideos(let path):
            return "No video files found under preprocess parity root: \(path)"
        }
    }
}

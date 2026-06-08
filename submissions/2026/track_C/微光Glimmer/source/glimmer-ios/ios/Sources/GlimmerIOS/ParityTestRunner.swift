import Foundation
import GlimmerCore

enum ParityTestRunner {
    private static var didStart = false
    private static let environment = ProcessInfo.processInfo.environment

    static func runIfConfigured() async {
        guard !didStart else { return }
        guard let mediaRootValue = environment["GLIMMER_PARITY_MEDIA_ROOT"],
              !mediaRootValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        didStart = true

        let outputValue = environment["GLIMMER_PARITY_OUTPUT"] ?? "Documents/parity_results.json"
        let mediaRoot = resolveContainerURL(mediaRootValue)
        let outputURL = resolveContainerURL(outputValue)

        do {
            let records = try await run(mediaRoot: mediaRoot)
            try write(records: records, outputURL: outputURL)
            print("GLIMMER_PARITY_RESULTS \(outputURL.path)")
        } catch {
            let failure = ParityRecord(
                sampleID: "__failure__",
                directoryPath: mediaRoot.path,
                frameCount: 0,
                audioPath: nil,
                mediaCount: 0,
                rawPrediction: nil,
                parsedJSON: nil,
                error: String(describing: error)
            )
            try? write(records: [failure], outputURL: outputURL)
            print("GLIMMER_PARITY_FAILURE \(String(describing: error))")
        }
    }

    private static func run(mediaRoot: URL) async throws -> [ParityRecord] {
        let modelFiles = try localModelFiles()
        let ownerID = UUID()
        let runner = AsdGgufRunner.shared
        try await runner.load(modelFiles: modelFiles, ownerID: ownerID)

        do {
            var records: [ParityRecord] = []
            for sampleDirectory in try sampleDirectories(mediaRoot: mediaRoot) {
                let frameURLs = try frameURLs(in: sampleDirectory)
                let audioURL = audioURL(in: sampleDirectory)
                let supportsAudio = await runner.supportsAudio(ownerID: ownerID)
                let request = AsdGgufRequestBuilder.build(
                    frameURLs: frameURLs,
                    audioURL: supportsAudio ? audioURL : nil,
                    userPrompt: AsdGgufPrompts.userInstruction
                )
                let raw = try await runner.generate(
                    systemPrompt: AsdGgufPrompts.system,
                    request: request,
                    ownerID: ownerID
                )
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                let parsed = AsdBehaviorParser.parse(raw)
                records.append(
                    ParityRecord(
                        sampleID: sampleID(from: sampleDirectory),
                        directoryPath: sampleDirectory.path,
                        frameCount: frameURLs.count,
                        audioPath: audioURL?.path,
                        mediaCount: request.mediaItems.count,
                        rawPrediction: raw,
                        parsedJSON: parsed?.jsonString,
                        error: nil
                    )
                )
            }
            await runner.shutdown(ownerID: ownerID)
            return records
        } catch {
            await runner.shutdown(ownerID: ownerID)
            throw error
        }
    }

    private static func localModelFiles() throws -> AsdGgufModelFiles {
        try ModelCatalog.resolvedModelFiles()
    }

    private static func sampleDirectories(mediaRoot: URL) throws -> [URL] {
        let fileManager = FileManager.default
        var isDirectory: ObjCBool = false
        guard fileManager.fileExists(atPath: mediaRoot.path, isDirectory: &isDirectory), isDirectory.boolValue else {
            throw ParityError.missingMediaRoot(mediaRoot.path)
        }
        let rootFrameURLs = try frameURLs(in: mediaRoot)
        if !rootFrameURLs.isEmpty {
            return [mediaRoot]
        }

        let children = try fileManager.contentsOfDirectory(
            at: mediaRoot,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        )

        var directories: [URL] = []
        for child in children.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) {
            let values = try child.resourceValues(forKeys: [.isDirectoryKey])
            guard values.isDirectory == true else {
                continue
            }
            let childFrameURLs = try frameURLs(in: child)
            if !childFrameURLs.isEmpty {
                directories.append(child)
            }
        }
        return directories
    }

    private static func frameURLs(in directory: URL) throws -> [URL] {
        try FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        )
        .filter { $0.pathExtension.lowercased() == "jpg" && $0.lastPathComponent.hasPrefix("frame_") }
        .sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    private static func audioURL(in directory: URL) -> URL? {
        let preferred = directory.appendingPathComponent("audio_16k_mono.wav")
        if FileManager.default.fileExists(atPath: preferred.path) {
            return preferred
        }
        let wavs = (try? FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        )) ?? []
        return wavs
            .filter { $0.pathExtension.lowercased() == "wav" }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
            .first
    }

    private static func sampleID(from directory: URL) -> String {
        let name = directory.lastPathComponent
        let pattern = #"^\d{4}_(.+)_[0-9a-f]{12}$"#
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: name, range: NSRange(name.startIndex..., in: name)),
              let range = Range(match.range(at: 1), in: name) else {
            return name
        }
        return String(name[range])
    }

    private static func resolveContainerURL(_ value: String) -> URL {
        if value.hasPrefix("/") {
            return URL(fileURLWithPath: value)
        }
        return URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(value)
    }

    private static func write(records: [ParityRecord], outputURL: URL) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(
            ParityResult(
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

private struct ParityResult: Codable {
    let generatedAt: String
    let records: [ParityRecord]
}

private struct ParityRecord: Codable {
    let sampleID: String
    let directoryPath: String
    let frameCount: Int
    let audioPath: String?
    let mediaCount: Int
    let rawPrediction: String?
    let parsedJSON: String?
    let error: String?
}

private enum ParityError: LocalizedError {
    case missingMediaRoot(String)

    var errorDescription: String? {
        switch self {
        case .missingMediaRoot(let path):
            return "Missing parity media root: \(path)"
        }
    }
}

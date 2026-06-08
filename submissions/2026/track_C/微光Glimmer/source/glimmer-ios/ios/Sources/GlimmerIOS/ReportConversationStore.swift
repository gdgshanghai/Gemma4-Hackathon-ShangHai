import Foundation
import GlimmerCore
import Observation

struct ReportConversationMedia {
    let videoURL: URL
    let frameURLs: [URL]
    let audioURL: URL?
}

struct ReportConversationRecord: Codable, Identifiable, Equatable {
    let id: UUID
    let createdAt: Date
    let timestamp: String
    let videoTitle: String
    let videoDuration: String
    let labelCode: String
    let language: GlimmerLanguage?
    let conclusion: String
    var messages: [ExplanationChatMessage]
    let videoFileName: String
    let frameFileNames: [String]
    let audioFileName: String?

    var report: AsdBehaviorReport? {
        AsdBehaviorParser.parse(labelCode)
    }

    var reportLanguage: GlimmerLanguage {
        language ?? .zh
    }
}

@MainActor
@Observable
final class ReportConversationStore {
    private(set) var records: [ReportConversationRecord] = []

    private let fileManager: FileManager
    private let rootDirectory: URL
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(fileManager: FileManager = .default, rootDirectory: URL? = nil) {
        self.fileManager = fileManager
        self.rootDirectory = rootDirectory ?? fileManager
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("GlimmerReports", isDirectory: true)
        self.encoder = JSONEncoder()
        self.encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        self.decoder = JSONDecoder()
    }

    func load() {
        do {
            try ensureRootDirectory()
            let directories = try fileManager.contentsOfDirectory(
                at: rootDirectory,
                includingPropertiesForKeys: [.isDirectoryKey],
                options: [.skipsHiddenFiles]
            )
            records = directories.compactMap { directory in
                let recordURL = recordURL(forDirectory: directory)
                guard let data = try? Data(contentsOf: recordURL) else { return nil }
                return try? decoder.decode(ReportConversationRecord.self, from: data)
            }
            sortRecords()
        } catch {
            records = []
        }
    }

    @discardableResult
    func createRecord(
        timestamp: String,
        videoURL: URL,
        videoDuration: String,
        report: AsdBehaviorReport,
        media: PreparedGgufMedia,
        language: GlimmerLanguage = .zh
    ) throws -> ReportConversationRecord {
        try ensureRootDirectory()

        let id = UUID()
        let directory = directoryURL(for: id)
        try fileManager.createDirectory(at: directory, withIntermediateDirectories: true)

        do {
            let videoFileName = try copyVideo(videoURL, into: directory)
            let frameFileNames = try copyFrames(media.frameURLs, into: directory)
            let audioFileName = try copyAudio(media.audioURL, into: directory)
            let record = ReportConversationRecord(
                id: id,
                createdAt: Date(),
                timestamp: timestamp,
                videoTitle: videoURL.lastPathComponent.isEmpty ? L10n.defaultVideoTitle(language) : videoURL.lastPathComponent,
                videoDuration: videoDuration,
                labelCode: report.labelCode,
                language: language,
                conclusion: report.conclusionText(language: language),
                messages: [],
                videoFileName: videoFileName,
                frameFileNames: frameFileNames,
                audioFileName: audioFileName
            )

            try writeRecord(record)
            records.append(record)
            sortRecords()
            return record
        } catch {
            try? fileManager.removeItem(at: directory)
            throw error
        }
    }

    func updateMessages(recordID: UUID, messages: [ExplanationChatMessage]) {
        guard let index = records.firstIndex(where: { $0.id == recordID }) else { return }
        records[index].messages = messages
        try? writeRecord(records[index])
    }

    func delete(_ record: ReportConversationRecord) {
        try? fileManager.removeItem(at: directoryURL(for: record.id))
        records.removeAll { $0.id == record.id }
    }

    func record(id: UUID) -> ReportConversationRecord? {
        records.first { $0.id == id }
    }

    func media(for record: ReportConversationRecord) -> ReportConversationMedia {
        let directory = directoryURL(for: record.id)
        let videoURL = directory.appendingPathComponent(record.videoFileName)
        let frameURLs = record.frameFileNames
            .map { directory.appendingPathComponent($0) }
            .filter { fileManager.fileExists(atPath: $0.path) }
        let audioURL = record.audioFileName
            .map { directory.appendingPathComponent($0) }
            .flatMap { fileManager.fileExists(atPath: $0.path) ? $0 : nil }
        return ReportConversationMedia(videoURL: videoURL, frameURLs: frameURLs, audioURL: audioURL)
    }

    private func ensureRootDirectory() throws {
        try fileManager.createDirectory(at: rootDirectory, withIntermediateDirectories: true)
    }

    private func directoryURL(for id: UUID) -> URL {
        rootDirectory.appendingPathComponent(id.uuidString, isDirectory: true)
    }

    private func recordURL(for record: ReportConversationRecord) -> URL {
        recordURL(forDirectory: directoryURL(for: record.id))
    }

    private func recordURL(forDirectory directory: URL) -> URL {
        directory.appendingPathComponent("record.json")
    }

    private func writeRecord(_ record: ReportConversationRecord) throws {
        let data = try encoder.encode(record)
        try data.write(to: recordURL(for: record), options: [.atomic])
    }

    private func sortRecords() {
        records.sort { $0.createdAt > $1.createdAt }
    }

    private func copyVideo(_ videoURL: URL, into directory: URL) throws -> String {
        let extensionName = videoURL.pathExtension.isEmpty ? "mp4" : videoURL.pathExtension
        let fileName = "video.\(extensionName)"
        try copyItem(from: videoURL, to: directory.appendingPathComponent(fileName))
        return fileName
    }

    private func copyFrames(_ frameURLs: [URL], into directory: URL) throws -> [String] {
        try frameURLs.enumerated().map { index, source in
            let extensionName = source.pathExtension.isEmpty ? "jpg" : source.pathExtension
            let fileName = String(format: "frame_%03d.%@", index, extensionName)
            try copyItem(from: source, to: directory.appendingPathComponent(fileName))
            return fileName
        }
    }

    private func copyAudio(_ audioURL: URL?, into directory: URL) throws -> String? {
        guard let audioURL else { return nil }
        let extensionName = audioURL.pathExtension.isEmpty ? "wav" : audioURL.pathExtension
        let fileName = "audio.\(extensionName)"
        try copyItem(from: audioURL, to: directory.appendingPathComponent(fileName))
        return fileName
    }

    private func copyItem(from source: URL, to destination: URL) throws {
        if fileManager.fileExists(atPath: destination.path) {
            try fileManager.removeItem(at: destination)
        }
        try fileManager.copyItem(at: source, to: destination)
    }
}

import GlimmerCore
import XCTest
@testable import GlimmerIOS

final class ReportConversationStoreTests: XCTestCase {
    func testCreateRecordCopiesOriginalVideoForPreview() async throws {
        let fileManager = FileManager.default
        let root = fileManager.temporaryDirectory
            .appendingPathComponent("GlimmerReportStoreTests-\(UUID().uuidString)", isDirectory: true)
        try fileManager.createDirectory(at: root, withIntermediateDirectories: true)
        defer {
            try? fileManager.removeItem(at: root)
        }

        let videoURL = root.appendingPathComponent("source.mov")
        let frameURL = root.appendingPathComponent("frame.jpg")
        let audioURL = root.appendingPathComponent("audio.wav")
        let videoData = Data("video bytes".utf8)
        let frameData = Data("frame bytes".utf8)
        let audioData = Data("audio bytes".utf8)
        try videoData.write(to: videoURL)
        try frameData.write(to: frameURL)
        try audioData.write(to: audioURL)

        let media = PreparedGgufMedia(
            frameURLs: [frameURL],
            audioURL: audioURL,
            diagnostics: GgufMediaDiagnostics(
                sourceVideoPath: videoURL.path,
                outputDirectoryPath: root.path,
                assetDurationSeconds: 1,
                durationSeconds: 1,
                durationSource: "test",
                requestedFrameCount: 1,
                frameDiagnostics: [],
                audioDiagnostics: nil
            )
        )

        try await MainActor.run {
            let report = try XCTUnwrap(AsdBehaviorParser.parse("000000000"))
            let store = ReportConversationStore(
                rootDirectory: root.appendingPathComponent("Reports", isDirectory: true)
            )

            let record = try store.createRecord(
                timestamp: "2026-06-06 19:00:00",
                videoURL: videoURL,
                videoDuration: "00:01",
                report: report,
                media: media,
                language: .en
            )
            let storedMedia = store.media(for: record)

            XCTAssertEqual(record.language, .en)
            XCTAssertEqual(record.reportLanguage, .en)
            XCTAssertTrue(record.conclusion.contains("did not observe clear behavior features"))
            XCTAssertEqual(record.videoFileName, "video.mov")
            XCTAssertTrue(FileManager.default.fileExists(atPath: storedMedia.videoURL.path))
            XCTAssertEqual(try Data(contentsOf: storedMedia.videoURL), videoData)
            XCTAssertEqual(storedMedia.frameURLs.count, 1)
            XCTAssertEqual(try XCTUnwrap(storedMedia.audioURL).lastPathComponent, "audio.wav")
        }
    }

    func testLegacyRecordWithoutLanguageDefaultsToChinese() throws {
        let data = Data(
            """
            {
              "id": "11111111-1111-1111-1111-111111111111",
              "createdAt": 739324800,
              "timestamp": "2026-06-06 19:00:00",
              "videoTitle": "video.mov",
              "videoDuration": "00:01",
              "labelCode": "000000000",
              "conclusion": "legacy",
              "messages": [],
              "videoFileName": "video.mov",
              "frameFileNames": [],
              "audioFileName": null
            }
            """.utf8
        )

        let record = try JSONDecoder().decode(ReportConversationRecord.self, from: data)

        XCTAssertNil(record.language)
        XCTAssertEqual(record.reportLanguage, .zh)
    }
}

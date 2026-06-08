import CryptoKit
import Foundation

struct PreparedGgufMedia {
    let frameURLs: [URL]
    let audioURL: URL?
    let diagnostics: GgufMediaDiagnostics
}

struct FrameExtractionResult {
    let frameURLs: [URL]
    let diagnostics: [GgufFrameDiagnostics]
}

struct AudioExtractionResult {
    let url: URL?
    let diagnostics: GgufAudioDiagnostics
}

struct GgufMediaDiagnostics: Codable {
    let sourceVideoPath: String
    let outputDirectoryPath: String
    let assetDurationSeconds: Double
    let durationSeconds: Double
    let durationSource: String
    let requestedFrameCount: Int
    let frameDiagnostics: [GgufFrameDiagnostics]
    let audioDiagnostics: GgufAudioDiagnostics?
}

struct GgufFrameDiagnostics: Codable {
    let index: Int
    let requestedTimeSeconds: Double
    let actualTimeSeconds: Double?
    let sourceWidth: Int?
    let sourceHeight: Int?
    let outputWidth: Int?
    let outputHeight: Int?
    let path: String?
    let byteCount: Int?
    let sha256: String?
    let error: String?
}

struct GgufAudioDiagnostics: Codable {
    let requestedDurationSeconds: Double
    let clippedDurationSeconds: Double
    let actualPcmDurationSeconds: Double?
    let sampleRate: Int
    let channels: Int
    let bitsPerSample: Int
    let path: String?
    let pcmByteCount: Int?
    let wavByteCount: Int?
    let sha256: String?
    let error: String?
}

enum MediaDiagnostics {
    static func sha256Hex(data: Data) -> String {
        SHA256.hash(data: data)
            .map { String(format: "%02x", $0) }
            .joined()
    }

    static func byteCount(fileURL: URL) -> Int? {
        guard let values = try? fileURL.resourceValues(forKeys: [.fileSizeKey]) else {
            return nil
        }
        return values.fileSize
    }
}

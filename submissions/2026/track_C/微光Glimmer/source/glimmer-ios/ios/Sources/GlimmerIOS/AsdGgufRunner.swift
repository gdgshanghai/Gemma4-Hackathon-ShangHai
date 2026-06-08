import Foundation
import Darwin
import GlimmerCore
import OSLog
@preconcurrency import AsdGgufNative

struct AsdGgufModelFiles: Equatable {
    let modelURL: URL
    let mmprojURL: URL
}

enum AsdGgufRunnerError: LocalizedError {
    case missingModel
    case missingMmproj
    case nativeLoadFailed
    case nativeGenerationFailed
    case staleSession

    var errorDescription: String? {
        switch self {
        case .missingModel:
            return "Missing GGUF model file."
        case .missingMmproj:
            return "Missing GGUF multimodal projector file."
        case .nativeLoadFailed:
            return "Failed to load the GGUF native runtime."
        case .nativeGenerationFailed:
            return "Failed to generate with the GGUF native runtime."
        case .staleSession:
            return "The GGUF runtime session is no longer active."
        }
    }
}

final class AsdGgufRunner: @unchecked Sendable {
    static let shared = AsdGgufRunner()

    private var modelFiles: AsdGgufModelFiles?
    private var nativeRunner: ASDGgufNativeRunner?
    private var lease = GgufRuntimeLease()
    private let inferenceQueue = DispatchQueue(label: "com.glimmer.asd.gguf.inference", qos: .userInitiated)
    private let logger = Logger(subsystem: "cn.enactflow.glimmer", category: "GgufRuntime")

    private init() {}

    func load(modelFiles: AsdGgufModelFiles, ownerID: UUID) async throws {
        guard FileManager.default.fileExists(atPath: modelFiles.modelURL.path) else {
            throw AsdGgufRunnerError.missingModel
        }
        guard FileManager.default.fileExists(atPath: modelFiles.mmprojURL.path) else {
            throw AsdGgufRunnerError.missingMmproj
        }

        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            inferenceQueue.async {
                self.lease.acquire(ownerID)

                if self.modelFiles == modelFiles, self.nativeRunner != nil {
                    self.logMemory("reuse loaded runtime")
                    continuation.resume()
                    return
                }

                self.logMemory("before runtime load")
                self.releaseNativeRunner()

                do {
                    self.nativeRunner = try autoreleasepool {
                        try ASDGgufNativeRunner(
                            modelPath: modelFiles.modelURL.path,
                            mmprojPath: modelFiles.mmprojURL.path
                        )
                    }
                    self.modelFiles = modelFiles
                    self.logMemory("after runtime load")
                    continuation.resume()
                } catch {
                    self.releaseNativeRunner()
                    _ = self.lease.release(ifOwnedBy: ownerID)
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    func supportsAudio(ownerID: UUID) async -> Bool {
        await withCheckedContinuation { continuation in
            inferenceQueue.async {
                let value = self.lease.isActive(ownerID) && (self.nativeRunner?.supportsAudio ?? false)
                continuation.resume(returning: value)
            }
        }
    }

    func generate(systemPrompt: String, request: AsdGgufRequest, ownerID: UUID) async throws -> String {
        let mediaPaths = request.mediaItems.map(\.url.path)
        return try await withCheckedThrowingContinuation { continuation in
            inferenceQueue.async {
                do {
                    let nativeRunner = try self.activeNativeRunner(ownerID: ownerID)
                    self.logMemory("before generate")
                    let output = try nativeRunner.generate(
                        withSystemPrompt: systemPrompt,
                        userPrompt: request.prompt,
                        mediaPaths: mediaPaths
                    )
                    self.logMemory("after generate")
                    continuation.resume(returning: output)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    func beginExplanationSession(
        systemPrompt: String,
        request: AsdGgufRequest,
        assistantContext: String,
        ownerID: UUID
    ) async throws {
        let mediaPaths = request.mediaItems.map(\.url.path)
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            inferenceQueue.async {
                do {
                    let nativeRunner = try self.activeNativeRunner(ownerID: ownerID)
                    nativeRunner.invalidateExplanationSession()
                    self.logMemory("before explanation prefill")
                    try nativeRunner.beginExplanationSession(
                        withSystemPrompt: systemPrompt,
                        userPrompt: request.prompt,
                        assistantContext: assistantContext,
                        mediaPaths: mediaPaths
                    )
                    self.logMemory("after explanation prefill")
                    continuation.resume()
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    func sendExplanationMessage(
        _ message: String,
        maxOutputTokens: Int = 512,
        ownerID: UUID
    ) async throws -> String {
        return try await withCheckedThrowingContinuation { continuation in
            inferenceQueue.async {
                do {
                    let nativeRunner = try self.activeNativeRunner(ownerID: ownerID)
                    let output = try nativeRunner.sendExplanationUserMessage(
                        message,
                        maxOutputTokens: maxOutputTokens
                    )
                    continuation.resume(returning: output)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    func invalidateExplanationSession(ownerID: UUID) async {
        await withCheckedContinuation { (continuation: CheckedContinuation<Void, Never>) in
            inferenceQueue.async {
                guard self.lease.isActive(ownerID), let nativeRunner = self.nativeRunner else {
                    continuation.resume()
                    return
                }
                nativeRunner.invalidateExplanationSession()
                continuation.resume()
            }
        }
    }

    func shutdown(ownerID: UUID) async {
        await withCheckedContinuation { (continuation: CheckedContinuation<Void, Never>) in
            inferenceQueue.async {
                guard self.lease.release(ifOwnedBy: ownerID) else {
                    continuation.resume()
                    return
                }

                self.logMemory("before runtime unload")
                self.releaseNativeRunner()
                self.logMemory("after runtime unload")
                continuation.resume()
            }
        }
    }

    private func activeNativeRunner(ownerID: UUID) throws -> ASDGgufNativeRunner {
        guard lease.isActive(ownerID) else {
            throw AsdGgufRunnerError.staleSession
        }
        guard let nativeRunner else {
            throw AsdGgufRunnerError.missingModel
        }
        return nativeRunner
    }

    private func releaseNativeRunner() {
        autoreleasepool {
            nativeRunner?.invalidateExplanationSession()
            nativeRunner = nil
            modelFiles = nil
        }
    }

    private func logMemory(_ event: String) {
        #if DEBUG
        if let bytes = Self.physicalFootprintBytes() {
            let megabytes = Double(bytes) / 1_048_576.0
            let formattedMegabytes = String(format: "%.1f", megabytes)
            logger.debug("\(event, privacy: .public): physical footprint \(formattedMegabytes, privacy: .public) MB")
        } else {
            logger.debug("\(event, privacy: .public): physical footprint unavailable")
        }
        #endif
    }

    private static func physicalFootprintBytes() -> UInt64? {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.stride / MemoryLayout<natural_t>.stride)
        let result = withUnsafeMutablePointer(to: &info) { pointer in
            pointer.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { rebound in
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), rebound, &count)
            }
        }
        guard result == KERN_SUCCESS else { return nil }
        return info.phys_footprint
    }
}

struct GgufRuntimeLease {
    private(set) var activeOwnerID: UUID?

    mutating func acquire(_ ownerID: UUID) {
        activeOwnerID = ownerID
    }

    func isActive(_ ownerID: UUID) -> Bool {
        activeOwnerID == ownerID
    }

    mutating func release(ifOwnedBy ownerID: UUID) -> Bool {
        guard isActive(ownerID) else { return false }
        activeOwnerID = nil
        return true
    }
}

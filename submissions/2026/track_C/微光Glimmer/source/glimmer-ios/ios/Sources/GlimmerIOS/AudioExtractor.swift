import AVFoundation
import Foundation
import GlimmerCore

enum AudioExtractor {
    static func extractWav(
        from videoURL: URL,
        durationSeconds: Double? = nil,
        outputDirectory: URL? = nil
    ) async -> AudioExtractionResult {
        let asset = AVURLAsset(url: videoURL)
        let duration: Double
        if let durationSeconds {
            duration = durationSeconds
        } else {
            duration = CMTimeGetSeconds((try? await asset.load(.duration)) ?? .zero)
        }
        let clippedDuration = AsdGgufContract.audioClipDuration(durationSeconds: duration)
        let baseDiagnostics = GgufAudioDiagnostics(
            requestedDurationSeconds: duration,
            clippedDurationSeconds: clippedDuration,
            actualPcmDurationSeconds: nil,
            sampleRate: 16000,
            channels: 1,
            bitsPerSample: 16,
            path: nil,
            pcmByteCount: nil,
            wavByteCount: nil,
            sha256: nil,
            error: nil
        )
        guard clippedDuration > 0 else {
            return AudioExtractionResult(
                url: nil,
                diagnostics: baseDiagnostics.with(error: "Invalid audio duration")
            )
        }
        guard let track = try? await asset.loadTracks(withMediaType: .audio).first else {
            return AudioExtractionResult(
                url: nil,
                diagnostics: baseDiagnostics.with(error: "Missing audio track")
            )
        }
        guard let reader = try? AVAssetReader(asset: asset) else {
            return AudioExtractionResult(
                url: nil,
                diagnostics: baseDiagnostics.with(error: "Failed to create AVAssetReader")
            )
        }
        reader.timeRange = CMTimeRange(
            start: .zero,
            duration: CMTime(seconds: clippedDuration, preferredTimescale: 1_000_000)
        )

        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsNonInterleaved: false,
        ]
        let output = AVAssetReaderTrackOutput(track: track, outputSettings: settings)
        guard reader.canAdd(output) else {
            return AudioExtractionResult(
                url: nil,
                diagnostics: baseDiagnostics.with(error: "Cannot add AVAssetReaderTrackOutput")
            )
        }
        reader.add(output)
        guard reader.startReading() else {
            return AudioExtractionResult(
                url: nil,
                diagnostics: baseDiagnostics.with(error: reader.error.map { String(describing: $0) } ?? "Failed to start reading")
            )
        }

        var pcm = Data()
        while let buffer = output.copyNextSampleBuffer() {
            if let block = CMSampleBufferGetDataBuffer(buffer) {
                let length = CMBlockBufferGetDataLength(block)
                var chunk = Data(count: length)
                let ok = chunk.withUnsafeMutableBytes { ptr -> Bool in
                    guard let base = ptr.baseAddress else { return false }
                    return CMBlockBufferCopyDataBytes(block, atOffset: 0, dataLength: length,
                                                      destination: base) == kCMBlockBufferNoErr
                }
                if ok { pcm.append(chunk) }
            }
            CMSampleBufferInvalidate(buffer)
        }
        guard !pcm.isEmpty else {
            return AudioExtractionResult(
                url: nil,
                diagnostics: baseDiagnostics.with(error: reader.error.map { String(describing: $0) } ?? "Empty PCM output")
            )
        }
        pcm = normalizePCM(
            pcm,
            targetDurationSeconds: clippedDuration,
            sampleRate: 16000,
            channels: 1,
            bitsPerSample: 16
        )

        let out = (outputDirectory ?? FileManager.default.temporaryDirectory)
            .appendingPathComponent("audio_16k_mono.wav")
        let wav = wavData(pcm: pcm, sampleRate: 16000, channels: 1, bitsPerSample: 16)
        do {
            try FileManager.default.createDirectory(
                at: out.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try wav.write(to: out, options: .atomic)
        } catch {
            return AudioExtractionResult(
                url: nil,
                diagnostics: baseDiagnostics.with(
                    path: out.path,
                    pcmByteCount: pcm.count,
                    wavByteCount: wav.count,
                    sha256: MediaDiagnostics.sha256Hex(data: wav),
                    error: String(describing: error)
                )
            )
        }

        let actualPcmDuration = Double(pcm.count) / Double(16000 * 1 * 16 / 8)
        return AudioExtractionResult(
            url: out,
            diagnostics: baseDiagnostics.with(
                actualPcmDurationSeconds: actualPcmDuration,
                path: out.path,
                pcmByteCount: pcm.count,
                wavByteCount: wav.count,
                sha256: MediaDiagnostics.sha256Hex(data: wav),
                error: nil
            )
        )
    }

    private static func wavData(pcm: Data, sampleRate: Int, channels: Int, bitsPerSample: Int) -> Data {
        let byteRate = sampleRate * channels * bitsPerSample / 8
        let blockAlign = channels * bitsPerSample / 8
        let dataSize = pcm.count
        var h = Data()
        func s(_ str: String) { h.append(str.data(using: .ascii)!) }
        func u32(_ v: UInt32) { var x = v.littleEndian; h.append(Data(bytes: &x, count: 4)) }
        func u16(_ v: UInt16) { var x = v.littleEndian; h.append(Data(bytes: &x, count: 2)) }
        s("RIFF"); u32(UInt32(36 + dataSize)); s("WAVE")
        s("fmt "); u32(16); u16(1); u16(UInt16(channels))
        u32(UInt32(sampleRate)); u32(UInt32(byteRate)); u16(UInt16(blockAlign)); u16(UInt16(bitsPerSample))
        s("data"); u32(UInt32(dataSize))
        var out = h; out.append(pcm); return out
    }

    private static func normalizePCM(
        _ pcm: Data,
        targetDurationSeconds: Double,
        sampleRate: Int,
        channels: Int,
        bitsPerSample: Int
    ) -> Data {
        let bytesPerSampleFrame = channels * bitsPerSample / 8
        let targetFrames = max(0, Int((targetDurationSeconds * Double(sampleRate)).rounded()))
        let targetBytes = targetFrames * bytesPerSampleFrame
        guard targetBytes > 0 else { return pcm }

        if pcm.count == targetBytes {
            return pcm
        }
        if pcm.count > targetBytes {
            return pcm.prefix(targetBytes)
        }

        var padded = pcm
        padded.append(Data(count: targetBytes - pcm.count))
        return padded
    }
}

private extension GgufAudioDiagnostics {
    func with(
        actualPcmDurationSeconds: Double? = nil,
        path: String? = nil,
        pcmByteCount: Int? = nil,
        wavByteCount: Int? = nil,
        sha256: String? = nil,
        error: String?
    ) -> GgufAudioDiagnostics {
        GgufAudioDiagnostics(
            requestedDurationSeconds: requestedDurationSeconds,
            clippedDurationSeconds: clippedDurationSeconds,
            actualPcmDurationSeconds: actualPcmDurationSeconds,
            sampleRate: sampleRate,
            channels: channels,
            bitsPerSample: bitsPerSample,
            path: path,
            pcmByteCount: pcmByteCount,
            wavByteCount: wavByteCount,
            sha256: sha256,
            error: error
        )
    }
}

import XCTest
@testable import GlimmerCore

final class AsdGgufContractTests: XCTestCase {
    func testGenerationConstantsMatchMacEval() {
        XCTAssertEqual(AsdGgufContract.promptLanguage, "zh")
        XCTAssertEqual(AsdGgufContract.contextSize, 8192)
        XCTAssertEqual(AsdGgufContract.frameFPS, 1.0)
        XCTAssertEqual(AsdGgufContract.maxFrames, 32)
        XCTAssertEqual(AsdGgufContract.imageWidth, 512)
        XCTAssertEqual(AsdGgufContract.maxAudioSeconds, 30.0)
        XCTAssertEqual(AsdGgufContract.maxOutputTokens, 16)
        XCTAssertEqual(AsdGgufContract.temperature, 0.0)
        XCTAssertEqual(AsdGgufContract.topK, 1)
        XCTAssertEqual(AsdGgufContract.topP, 1.0)
        XCTAssertEqual(AsdGgufContract.mediaMarker, "<__media__>")
        XCTAssertEqual(
            AsdGgufContract.code9Grammar,
            """
            root ::= bit bit bit bit bit bit bit bit bit
            bit ::= "0" | "1"
            """
        )
    }

    func testFrameCountMatchesMacEval() {
        XCTAssertEqual(AsdGgufContract.requestedFrameCount(durationSeconds: 3.0), 3)
        XCTAssertEqual(AsdGgufContract.requestedFrameCount(durationSeconds: 3.01), 4)
        XCTAssertEqual(AsdGgufContract.requestedFrameCount(durationSeconds: 50.53), 32)
        XCTAssertEqual(AsdGgufContract.requestedFrameCount(durationSeconds: 0.0), 1)
        XCTAssertEqual(AsdGgufContract.requestedFrameCount(durationSeconds: -1.0), 1)
    }

    func testSamplingScheduleMatchesMacEval() {
        XCTAssertEqual(AsdGgufContract.effectiveFrameFPS(frameCount: 3, durationSeconds: 3.0), 1.0)
        XCTAssertEqual(AsdGgufContract.sampleTime(frameIndex: 0, frameCount: 4, durationSeconds: 4.0), 0.0)
        XCTAssertEqual(AsdGgufContract.sampleTime(frameIndex: 1, frameCount: 4, durationSeconds: 4.0), 1.0)
        XCTAssertEqual(AsdGgufContract.sampleTime(frameIndex: 3, frameCount: 4, durationSeconds: 4.0), 3.0)
        XCTAssertEqual(AsdGgufContract.sampleTimes(frameCount: 4, durationSeconds: 4.0), [0.0, 1.0, 2.0, 3.0])
        XCTAssertEqual(AsdGgufContract.sampleTimes(frameCount: 0, durationSeconds: 4.0), [])
    }

    func testScaledImageSizeMatchesFfmpegScale512Minus2() {
        XCTAssertEqual(
            AsdGgufContract.scaledImageSize(sourceWidth: 1920, sourceHeight: 1080),
            AsdGgufScaledImageSize(width: 512, height: 288)
        )
        XCTAssertEqual(
            AsdGgufContract.scaledImageSize(sourceWidth: 300, sourceHeight: 200),
            AsdGgufScaledImageSize(width: 512, height: 342)
        )
        XCTAssertEqual(
            AsdGgufContract.scaledImageSize(sourceWidth: 1000, sourceHeight: 333),
            AsdGgufScaledImageSize(width: 512, height: 170)
        )
        XCTAssertEqual(
            AsdGgufContract.scaledImageSize(sourceWidth: 333, sourceHeight: 1000),
            AsdGgufScaledImageSize(width: 512, height: 1538)
        )
    }

    func testASDDSFilenameDurationParsing() {
        XCTAssertEqual(AsdGgufContract.asdDSClipDurationSeconds(fileStem: "6eS2CBMSZ4E_250_260"), 10)
        XCTAssertEqual(AsdGgufContract.asdDSClipDurationSeconds(fileStem: "E-XgK_LaFKI_11_21"), 10)
        XCTAssertNil(AsdGgufContract.asdDSClipDurationSeconds(fileStem: "user_video"))
        XCTAssertNil(AsdGgufContract.asdDSClipDurationSeconds(fileStem: "clip_20_10"))
    }

    func testAudioDurationMatchesMacEval() {
        XCTAssertEqual(AsdGgufContract.audioClipDuration(durationSeconds: 3.0), 3.0)
        XCTAssertEqual(AsdGgufContract.audioClipDuration(durationSeconds: 45.0), 30.0)
    }

    func testMediaPromptOrderMatchesServerRequest() {
        XCTAssertEqual(
            AsdGgufContract.promptWithMediaMarkers(mediaCount: 4, userPrompt: "instruction"),
            "<__media__><__media__><__media__><__media__>instruction"
        )
        XCTAssertEqual(AsdGgufContract.promptWithMediaMarkers(mediaCount: 0, userPrompt: "instruction"), "instruction")
    }
}

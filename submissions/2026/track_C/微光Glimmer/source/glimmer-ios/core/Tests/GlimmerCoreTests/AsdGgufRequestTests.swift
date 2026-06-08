import XCTest
@testable import GlimmerCore

final class AsdGgufRequestTests: XCTestCase {
    func testBuildsFrameAudioTextOrder() {
        let frames = [
            URL(fileURLWithPath: "/tmp/frame_0000.jpg"),
            URL(fileURLWithPath: "/tmp/frame_0001.jpg")
        ]
        let audio = URL(fileURLWithPath: "/tmp/audio_16k_mono.wav")

        let request = AsdGgufRequestBuilder.build(
            frameURLs: frames,
            audioURL: audio,
            userPrompt: "instruction"
        )

        XCTAssertEqual(request.mediaItems.map(\.kind), [.image, .image, .audio])
        XCTAssertEqual(request.mediaItems.map(\.url), frames + [audio])
        XCTAssertEqual(
            request.prompt,
            "<__media__><__media__><__media__>instruction"
        )
    }

    func testBuildsVisualOnlyOrder() {
        let frames = [URL(fileURLWithPath: "/tmp/frame_0000.jpg")]

        let request = AsdGgufRequestBuilder.build(
            frameURLs: frames,
            audioURL: nil,
            userPrompt: "instruction"
        )

        XCTAssertEqual(request.mediaItems.map(\.kind), [.image])
        XCTAssertEqual(request.mediaItems.map(\.url), frames)
        XCTAssertEqual(request.prompt, "<__media__>instruction")
    }
}

import Foundation

public enum AsdGgufMediaKind: Equatable, Sendable {
    case image
    case audio
}

public struct AsdGgufMediaItem: Equatable, Sendable {
    public let kind: AsdGgufMediaKind
    public let url: URL
}

public struct AsdGgufRequest: Equatable, Sendable {
    public let mediaItems: [AsdGgufMediaItem]
    public let userPrompt: String

    public var prompt: String {
        AsdGgufContract.promptWithMediaMarkers(mediaCount: mediaItems.count, userPrompt: userPrompt)
    }
}

public enum AsdGgufRequestBuilder {
    public static func build(frameURLs: [URL], audioURL: URL?, userPrompt: String) -> AsdGgufRequest {
        var mediaItems = frameURLs.map { AsdGgufMediaItem(kind: .image, url: $0) }
        if let audioURL {
            mediaItems.append(AsdGgufMediaItem(kind: .audio, url: audioURL))
        }
        return AsdGgufRequest(mediaItems: mediaItems, userPrompt: userPrompt)
    }
}

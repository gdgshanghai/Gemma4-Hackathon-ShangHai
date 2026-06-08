import Foundation

public enum GlimmerLanguage: String, Codable, CaseIterable, Equatable, Sendable {
    case zh
    case en

    public static var fallback: GlimmerLanguage { .zh }
}

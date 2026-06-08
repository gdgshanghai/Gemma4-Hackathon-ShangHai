// swift-tools-version: 5.9

import PackageDescription
import Foundation

let packageRoot = URL(fileURLWithPath: #filePath).deletingLastPathComponent().path
let macDylibPath =
    "\(packageRoot)/.build/artifacts/asd-litert-cli/CLiteRTLM_mac/CLiteRTLM_mac.xcframework/macos-arm64_x86_64/CLiteRTLM_mac.dylib"

let package = Package(
    name: "ASDLiteRTCLI",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "asd-litert-cli", targets: ["ASDLiteRTCLI"])
    ],
    targets: [
        .binaryTarget(
            name: "CLiteRTLM",
            url: "https://github.com/google-ai-edge/LiteRT-LM/releases/download/v0.12.0/CLiteRTLM.xcframework.zip",
            checksum: "3c2a11ecc8511d1e74efa7ca308dc7130c95223325c33212337ffb0563b79cde"
        ),
        .binaryTarget(
            name: "CLiteRTLM_mac",
            url: "https://github.com/google-ai-edge/LiteRT-LM/releases/download/v0.12.0/CLiteRTLM_mac.xcframework.zip",
            checksum: "a8238da94b31ce0383e0fd52a0a729b9c18a1055170a995f0aa32056bd9822e5"
        ),
        .target(
            name: "LiteRTLM",
            dependencies: [
                .target(name: "CLiteRTLM", condition: .when(platforms: [.iOS])),
                .target(name: "CLiteRTLM_mac", condition: .when(platforms: [.macOS]))
            ],
            linkerSettings: [
                .unsafeFlags(["-Xlinker", "-all_load", "-Xlinker", macDylibPath])
            ]
        ),
        .executableTarget(
            name: "ASDLiteRTCLI",
            dependencies: [
                "LiteRTLM"
            ]
        )
    ]
)

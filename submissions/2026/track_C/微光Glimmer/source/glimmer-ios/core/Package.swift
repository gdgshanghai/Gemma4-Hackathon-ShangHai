// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "GlimmerCore",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "GlimmerCore",
            targets: ["GlimmerCore"]
        )
    ],
    targets: [
        .target(
            name: "GlimmerCore",
            path: "Sources/GlimmerCore"
        ),
        .testTarget(
            name: "GlimmerCoreTests",
            dependencies: ["GlimmerCore"],
            path: "Tests/GlimmerCoreTests"
        )
    ]
)

// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "GlimmerIOS",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "GlimmerIOS",
            targets: ["GlimmerIOS"]
        )
    ],
    dependencies: [
        .package(path: "../core")
    ],
    targets: [
        .binaryTarget(
            name: "llama",
            path: "Vendor/llama.xcframework"
        ),
        .target(
            name: "AsdGgufNative",
            dependencies: ["llama"],
            path: "Sources/AsdGgufNative",
            publicHeadersPath: "include",
            linkerSettings: [
                .linkedLibrary("c++"),
                .linkedFramework("Accelerate"),
                .linkedFramework("Foundation"),
                .linkedFramework("Metal")
            ]
        ),
        .target(
            name: "GlimmerIOS",
            dependencies: [
                "AsdGgufNative",
                .product(name: "GlimmerCore", package: "core")
            ],
            path: "Sources/GlimmerIOS"
        ),
        .testTarget(
            name: "GlimmerIOSTests",
            dependencies: ["GlimmerIOS"],
            path: "Tests/GlimmerIOSTests"
        )
    ],
    cxxLanguageStandard: .cxx17
)

// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "WyckoffMac",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "WyckoffMac", targets: ["WyckoffMac"]),
        .executable(name: "MarkdownSmokeTest", targets: ["MarkdownSmokeTest"]),
    ],
    targets: [
        .executableTarget(
            name: "WyckoffMac",
            dependencies: ["WyckoffMacCore"],
            path: "Sources/WyckoffMac"
        ),
        .target(
            name: "WyckoffMacCore",
            path: "Sources/WyckoffMacCore"
        ),
        .executableTarget(
            name: "MarkdownSmokeTest",
            dependencies: ["WyckoffMacCore"],
            path: "Tests/MarkdownSmokeTest"
        ),
    ]
)

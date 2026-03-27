// swift-tools-version: 5.9
// Package.swift — shared models & services for Linux CI validation
import PackageDescription

let package = Package(
    name: "JessicAiMedusaCyberstackCore",
    platforms: [
        .iOS(.v16),
        .macOS(.v13),
    ],
    products: [
        .library(
            name: "JessicAiMedusaCyberstackCore",
            targets: ["JessicAiMedusaCyberstackCore"]
        ),
    ],
    dependencies: [],
    targets: [
        .target(
            name: "JessicAiMedusaCyberstackCore",
            path: "ios/JessicAiMedusaCyberstack",
            exclude: [
                "Views",
                "Resources",
                "JessicAiMedusaCyberstackApp.swift",
                "AppState.swift",
                "Services/BLEManager.swift",
                "Services/GeofenceManager.swift",
            ],
            sources: [
                "Models/LoRaNode.swift",
                "Models/BLEDevice.swift",
                "Models/GeofenceZone.swift",
                "Models/AIDecision.swift",
                "Models/ESP32Device.swift",
            ],
            swiftSettings: [
                .define("SWIFT_PACKAGE"),
            ]
        ),
        .testTarget(
            name: "JessicAiMedusaCyberstackCoreTests",
            dependencies: ["JessicAiMedusaCyberstackCore"],
            path: "ios/JessicAiMedusaCyberstackTests",
            exclude: ["JessicAiMedusaCyberstackTests.swift"]
        ),
    ]
)

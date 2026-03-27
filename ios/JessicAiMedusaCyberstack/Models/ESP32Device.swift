import Foundation

struct ESP32Device: Identifiable, Codable {
    let id: UUID
    var name: String
    var model: ESP32Model
    var firmwareVersion: String
    var flashSize: Int
    var ramSize: Int
    var cpuFrequency: Int
    var isConnected: Bool
    var ipAddress: String?
    var macAddress: String
    var uptimeSeconds: TimeInterval
    var errorLog: [FirmwareError]
    var lastFlashDate: Date?

    enum ESP32Model: String, Codable, CaseIterable {
        case esp32 = "ESP32"
        case esp32s2 = "ESP32-S2"
        case esp32s3 = "ESP32-S3"
        case esp32c3 = "ESP32-C3"
        case esp32h2 = "ESP32-H2"
    }
}

struct FirmwareError: Identifiable, Codable {
    let id: UUID
    var code: String
    var message: String
    var timestamp: Date
    var isResolved: Bool
    var resolution: String?
}

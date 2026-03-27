import Foundation
import SwiftUI
import CoreBluetooth

struct BLEDevice: Identifiable, Codable {
    let id: UUID
    var identifier: UUID
    var name: String
    var rssi: Int
    var isConnected: Bool
    var deviceType: DeviceType
    var lastSeen: Date
    var services: [String]

    enum DeviceType: String, Codable, CaseIterable {
        case flipperZero = "Flipper Zero"
        case nrfModule = "NRF Module"
        case esp32 = "ESP32"
        case generic = "Generic BLE"

        var icon: String {
            switch self {
            case .flipperZero: return "wand.and.rays"
            case .nrfModule: return "cpu.fill"
            case .esp32: return "memorychip"
            case .generic: return "dot.radiowaves.left.and.right"
            }
        }

        var color: Color {
            switch self {
            case .flipperZero: return .orange
            case .nrfModule: return .blue
            case .esp32: return .cyan
            case .generic: return .gray
            }
        }
    }
}

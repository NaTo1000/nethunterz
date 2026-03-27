import Foundation
import Combine

@MainActor
final class ESP32FirmwareService: ObservableObject {
    static let shared = ESP32FirmwareService()

    @Published var devices: [ESP32Device] = []
    @Published var currentVersion: String = "v1.2.2"
    @Published var latestVersion: String = "v1.2.3"
    @Published var updateAvailable: Bool = true
    @Published var isFlashing: Bool = false
    @Published var flashProgress: Double = 0

    private init() { loadMockDevices() }

    func installUpdate() async {
        isFlashing = true
        flashProgress = 0
        for i in 1...20 {
            try? await Task.sleep(nanoseconds: 200_000_000)
            flashProgress = Double(i) / 20.0
        }
        currentVersion = latestVersion
        updateAvailable = false
        isFlashing = false
    }

    func flashDevice(_ device: ESP32Device) async {
        isFlashing = true
        flashProgress = 0
        for i in 1...20 {
            try? await Task.sleep(nanoseconds: 300_000_000)
            flashProgress = Double(i) / 20.0
        }
        isFlashing = false
    }

    private func loadMockDevices() {
        devices = [
            ESP32Device(
                id: UUID(),
                name: "ESP32-Main",
                model: .esp32s3,
                firmwareVersion: "v1.2.2",
                flashSize: 8,
                ramSize: 512,
                cpuFrequency: 240,
                isConnected: true,
                macAddress: "AA:BB:CC:DD:EE:FF",
                uptimeSeconds: 86400,
                errorLog: [],
                lastFlashDate: nil
            )
        ]
    }
}

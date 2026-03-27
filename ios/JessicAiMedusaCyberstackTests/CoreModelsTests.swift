import XCTest
@testable import JessicAiMedusaCyberstackCore

/// SPM-compatible unit tests for the core model layer.
/// These tests run via `swift test` on macOS 13+ without Xcode.
final class CoreModelsTests: XCTestCase {

    // MARK: - LoRaNode

    func testLoRaNodeDefaultValues() {
        let node = LoRaNode(name: "NODE-001", rssi: -72, snr: 8.5)
        XCTAssertFalse(node.id == UUID(uuidString: "00000000-0000-0000-0000-000000000000")!)
        XCTAssertEqual(node.name, "NODE-001")
        XCTAssertEqual(node.rssi, -72)
        XCTAssertEqual(node.snr, 8.5)
        XCTAssertEqual(node.frequency, "915 MHz")
        XCTAssertEqual(node.batteryLevel, 100)
        XCTAssertFalse(node.isRelay)
    }

    func testLoRaNodeShortId() {
        let node = LoRaNode(name: "NODE-001", rssi: -72, snr: 8.5)
        XCTAssertEqual(node.shortId, "NODE")
    }

    func testLoRaNodeFormattedUptime() {
        let node = LoRaNode(name: "NODE-001", rssi: -72, snr: 8.5, uptimeSeconds: 3661)
        XCTAssertEqual(node.formattedUptime, "1h 1m")
    }

    func testLoRaNodeFormattedUptimeZero() {
        let node = LoRaNode(name: "NODE-001", rssi: -72, snr: 8.5, uptimeSeconds: 0)
        XCTAssertEqual(node.formattedUptime, "0h 0m")
    }

    func testLoRaNodeCodableRoundTrip() throws {
        let node = LoRaNode(
            name: "NODE-TEST",
            rssi: -80,
            snr: 6.0,
            frequency: "915 MHz (Half)",
            batteryLevel: 75,
            isRelay: true,
            uptimeSeconds: 7200
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(node)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(LoRaNode.self, from: data)

        XCTAssertEqual(decoded.id, node.id)
        XCTAssertEqual(decoded.name, node.name)
        XCTAssertEqual(decoded.rssi, node.rssi)
        XCTAssertEqual(decoded.snr, node.snr)
        XCTAssertEqual(decoded.frequency, node.frequency)
        XCTAssertEqual(decoded.batteryLevel, node.batteryLevel)
        XCTAssertEqual(decoded.isRelay, node.isRelay)
        XCTAssertEqual(decoded.uptimeSeconds, node.uptimeSeconds)
    }

    // MARK: - BLEDevice

    func testBLEDeviceTypeIcons() {
        XCTAssertEqual(BLEDevice.DeviceType.flipperZero.icon, "wand.and.rays")
        XCTAssertEqual(BLEDevice.DeviceType.nrfModule.icon, "cpu.fill")
        XCTAssertEqual(BLEDevice.DeviceType.esp32.icon, "memorychip")
        XCTAssertEqual(BLEDevice.DeviceType.generic.icon, "dot.radiowaves.left.and.right")
    }

    func testBLEDeviceTypeRawValues() {
        XCTAssertEqual(BLEDevice.DeviceType.flipperZero.rawValue, "Flipper Zero")
        XCTAssertEqual(BLEDevice.DeviceType.nrfModule.rawValue, "NRF Module")
        XCTAssertEqual(BLEDevice.DeviceType.esp32.rawValue, "ESP32")
        XCTAssertEqual(BLEDevice.DeviceType.generic.rawValue, "Generic BLE")
    }

    func testBLEDeviceCodable() throws {
        let device = BLEDevice(
            id: UUID(),
            identifier: UUID(),
            name: "Flipper Zero",
            rssi: -55,
            isConnected: true,
            deviceType: .flipperZero,
            lastSeen: Date(timeIntervalSince1970: 0),
            services: ["180D", "180F"]
        )
        let data = try JSONEncoder().encode(device)
        let decoded = try JSONDecoder().decode(BLEDevice.self, from: data)
        XCTAssertEqual(decoded.id, device.id)
        XCTAssertEqual(decoded.name, device.name)
        XCTAssertEqual(decoded.deviceType, .flipperZero)
        XCTAssertTrue(decoded.isConnected)
    }

    // MARK: - AIDecision

    func testAIDecisionSeverityRawValues() {
        XCTAssertEqual(AIDecision.Severity.low.rawValue, "Low")
        XCTAssertEqual(AIDecision.Severity.medium.rawValue, "Medium")
        XCTAssertEqual(AIDecision.Severity.high.rawValue, "High")
        XCTAssertEqual(AIDecision.Severity.critical.rawValue, "Critical")
    }

    func testAIDecisionOutcomeRawValues() {
        XCTAssertEqual(AIDecision.Outcome.pending.rawValue, "Pending")
        XCTAssertEqual(AIDecision.Outcome.success.rawValue, "Success")
        XCTAssertEqual(AIDecision.Outcome.failed.rawValue, "Failed")
        XCTAssertEqual(AIDecision.Outcome.mitigated.rawValue, "Mitigated")
    }

    func testAIDecisionCategoryIcons() {
        XCTAssertFalse(AIDecision.Category.meshOptimization.icon.isEmpty)
        XCTAssertFalse(AIDecision.Category.security.icon.isEmpty)
        XCTAssertFalse(AIDecision.Category.firmware.icon.isEmpty)
        XCTAssertFalse(AIDecision.Category.geofence.icon.isEmpty)
        XCTAssertFalse(AIDecision.Category.error.icon.isEmpty)
    }

    func testAIDecisionCodable() throws {
        let decision = AIDecision(
            id: UUID(),
            action: "Test action",
            reasoning: "Test reasoning",
            timestamp: Date(timeIntervalSince1970: 0),
            severity: .high,
            category: .security,
            outcome: .success,
            actions: ["Step 1", "Step 2"],
            confidenceScore: 0.95
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(decision)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(AIDecision.self, from: data)

        XCTAssertEqual(decoded.id, decision.id)
        XCTAssertEqual(decoded.action, decision.action)
        XCTAssertEqual(decoded.severity, .high)
        XCTAssertEqual(decoded.category, .security)
        XCTAssertEqual(decoded.outcome, .success)
        XCTAssertEqual(decoded.actions, ["Step 1", "Step 2"])
        XCTAssertEqual(decoded.confidenceScore, 0.95, accuracy: 0.001)
    }

    // MARK: - ESP32Device

    func testESP32DeviceModels() {
        XCTAssertEqual(ESP32Device.ESP32Model.esp32.rawValue, "ESP32")
        XCTAssertEqual(ESP32Device.ESP32Model.esp32s2.rawValue, "ESP32-S2")
        XCTAssertEqual(ESP32Device.ESP32Model.esp32s3.rawValue, "ESP32-S3")
        XCTAssertEqual(ESP32Device.ESP32Model.esp32c3.rawValue, "ESP32-C3")
        XCTAssertEqual(ESP32Device.ESP32Model.esp32h2.rawValue, "ESP32-H2")
    }

    func testESP32DeviceCodable() throws {
        let device = ESP32Device(
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
            errorLog: []
        )
        let data = try JSONEncoder().encode(device)
        let decoded = try JSONDecoder().decode(ESP32Device.self, from: data)
        XCTAssertEqual(decoded.id, device.id)
        XCTAssertEqual(decoded.model, .esp32s3)
        XCTAssertEqual(decoded.firmwareVersion, "v1.2.2")
        XCTAssertEqual(decoded.macAddress, "AA:BB:CC:DD:EE:FF")
    }

    // MARK: - MeshMessage

    func testMeshMessageDirection() {
        let incoming = MeshMessage(
            id: UUID(), payload: "hello", sourceNode: "A",
            destinationNode: "B", timestamp: Date(),
            direction: .incoming, hopCount: 2
        )
        XCTAssertEqual(incoming.direction, .incoming)

        let outgoing = MeshMessage(
            id: UUID(), payload: "reply", sourceNode: "B",
            destinationNode: "A", timestamp: Date(),
            direction: .outgoing, hopCount: 1
        )
        XCTAssertEqual(outgoing.direction, .outgoing)
    }
}

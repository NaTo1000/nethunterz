import XCTest
@testable import JessicAiMedusaCyberstack

final class JessicAiMedusaCyberstackTests: XCTestCase {

    // MARK: - AppState Tests

    func testAppStateInitialValues() {
        let appState = AppState()
        XCTAssertFalse(appState.isAuthenticated)
        XCTAssertEqual(appState.colorScheme, .dark)
        XCTAssertTrue(appState.activeAlerts.isEmpty)
        XCTAssertEqual(appState.connectionStatus, .disconnected)
    }

    func testPostAlertAddsAlert() async {
        let appState = AppState()
        let alert = SystemAlert(
            title: "Test Alert",
            message: "This is a test",
            severity: .info,
            timestamp: Date()
        )
        appState.postAlert(alert)
        XCTAssertEqual(appState.activeAlerts.count, 1)
        XCTAssertEqual(appState.activeAlerts.first?.title, "Test Alert")
    }

    // MARK: - LoRaNode Tests

    func testLoRaNodeShortId() {
        let node = LoRaNode(name: "NODE-001", rssi: -72, snr: 8.5)
        XCTAssertEqual(node.shortId, "NODE")
    }

    func testLoRaNodeFormattedUptime() {
        let node = LoRaNode(name: "NODE-001", rssi: -72, snr: 8.5, uptimeSeconds: 3661)
        XCTAssertEqual(node.formattedUptime, "1h 1m")
    }

    func testLoRaNodeCodable() throws {
        let node = LoRaNode(
            name: "NODE-TEST",
            rssi: -80,
            snr: 6.0,
            frequency: "915 MHz (Half)",
            batteryLevel: 75,
            isRelay: true
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
        XCTAssertEqual(decoded.isRelay, node.isRelay)
        XCTAssertEqual(decoded.batteryLevel, node.batteryLevel)
    }

    // MARK: - GeofenceZone Tests

    func testGeofenceZoneStatusColor() {
        var zone = GeofenceZone(
            name: "Test Zone",
            center: .init(latitude: 0, longitude: 0),
            radius: 100
        )
        zone.status = .safe
        XCTAssertNotNil(zone.statusColor)

        zone.status = .warning
        XCTAssertNotNil(zone.statusColor)

        zone.status = .breach
        XCTAssertNotNil(zone.statusColor)
    }

    func testGeofenceZoneCodable() throws {
        let zone = GeofenceZone(
            name: "HQ Perimeter",
            center: .init(latitude: 37.7749, longitude: -122.4194),
            radius: 200,
            status: .safe,
            attackMirrorEnabled: true
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let data = try encoder.encode(zone)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let decoded = try decoder.decode(GeofenceZone.self, from: data)

        XCTAssertEqual(decoded.id, zone.id)
        XCTAssertEqual(decoded.name, zone.name)
        XCTAssertEqual(decoded.radius, zone.radius)
        XCTAssertEqual(decoded.center.latitude, zone.center.latitude, accuracy: 0.0001)
        XCTAssertEqual(decoded.center.longitude, zone.center.longitude, accuracy: 0.0001)
    }

    // MARK: - AIDecision Tests

    func testAIDecisionSeverityColors() {
        let severities: [AIDecision.Severity] = [.low, .medium, .high, .critical]
        for severity in severities {
            XCTAssertNotNil(severity.color)
        }
    }

    func testAIDecisionOutcomeColors() {
        let outcomes: [AIDecision.Outcome] = [.pending, .success, .failed, .mitigated]
        for outcome in outcomes {
            XCTAssertNotNil(outcome.color)
        }
    }

    func testAIDecisionCategoryIcons() {
        let categories: [AIDecision.Category] = [.meshOptimization, .security, .firmware, .geofence, .error]
        for category in categories {
            XCTAssertFalse(category.icon.isEmpty)
        }
    }

    // MARK: - BLEDevice Tests

    func testBLEDeviceTypeIcons() {
        let types: [BLEDevice.DeviceType] = [.flipperZero, .nrfModule, .esp32, .generic]
        for type_ in types {
            XCTAssertFalse(type_.icon.isEmpty)
        }
    }

    // MARK: - ConnectionStatus Tests

    func testConnectionStatusRawValues() {
        XCTAssertEqual(ConnectionStatus.connected.rawValue, "Connected")
        XCTAssertEqual(ConnectionStatus.disconnected.rawValue, "Disconnected")
        XCTAssertEqual(ConnectionStatus.scanning.rawValue, "Scanning")
    }

    // MARK: - LoRaManager Tests

    @MainActor
    func testLoRaManagerInitialState() {
        let manager = LoRaManager.shared
        XCTAssertFalse(manager.connectedNodes.isEmpty, "Mock data should be loaded")
        XCTAssertEqual(manager.currentFrequency, "915 MHz (Half)")
        XCTAssertEqual(manager.spreadingFactor, 9)
        XCTAssertEqual(manager.txPower, 14)
    }

    @MainActor
    func testLoRaManagerSendMessage() async {
        let manager = LoRaManager.shared
        let initialCount = manager.recentMessages.count
        await manager.sendMessage("Hello mesh", to: "NODE-001")
        XCTAssertEqual(manager.recentMessages.count, initialCount + 1)
        XCTAssertEqual(manager.recentMessages.first?.payload, "Hello mesh")
    }

    // MARK: - AIOrchestrator Tests

    @MainActor
    func testAIOrchestratorInitialState() {
        let orchestrator = AIOrchestrator.shared
        XCTAssertFalse(orchestrator.recentDecisions.isEmpty)
        XCTAssertGreaterThan(orchestrator.decisionsToday, 0)
        XCTAssertGreaterThan(orchestrator.confidenceScore, 0)
        XCTAssertLessThanOrEqual(orchestrator.confidenceScore, 1)
    }

    @MainActor
    func testAIOrchestratorExecuteCommand() async {
        let orchestrator = AIOrchestrator.shared
        let initialCount = orchestrator.recentDecisions.count
        let initialDecisionsToday = orchestrator.decisionsToday
        await orchestrator.executeCommand("scan mesh")
        XCTAssertEqual(orchestrator.recentDecisions.count, initialCount + 1)
        XCTAssertEqual(orchestrator.decisionsToday, initialDecisionsToday + 1)
    }

    // MARK: - ESP32FirmwareService Tests

    @MainActor
    func testESP32FirmwareServiceInitialState() {
        let service = ESP32FirmwareService.shared
        XCTAssertFalse(service.devices.isEmpty)
        XCTAssertTrue(service.updateAvailable)
        XCTAssertNotEqual(service.currentVersion, service.latestVersion)
    }
}

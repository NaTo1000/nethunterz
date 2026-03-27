import Foundation
import Combine

@MainActor
final class LoRaManager: ObservableObject {
    static let shared = LoRaManager()

    @Published var connectedNodes: [LoRaNode] = []
    @Published var recentMessages: [MeshMessage] = []
    @Published var currentFrequency: String = "915 MHz (Half)"
    @Published var spreadingFactor: Int = 9
    @Published var txPower: Int = 14
    @Published var maxHopCount: Int = 5
    @Published var signalStrength: Double = -75.0
    @Published var beaconModeEnabled: Bool = false
    @Published var isMeshScanning: Bool = false

    private var cancellables = Set<AnyCancellable>()

    private init() { loadMockData() }

    func startMeshScan() async {
        isMeshScanning = true
        // Simulate mesh scanning with seek-and-find on half frequencies
        try? await Task.sleep(nanoseconds: 2_000_000_000)
        let mockNode = LoRaNode(
            name: "NODE-\(Int.random(in: 100...999))",
            rssi: Double.random(in: -120 ... -60),
            snr: Double.random(in: -5...15),
            frequency: currentFrequency,
            batteryLevel: Int.random(in: 20...100),
            isRelay: Bool.random()
        )
        connectedNodes.append(mockNode)
        isMeshScanning = false
    }

    func sendMessage(_ payload: String, to destination: String) async {
        let msg = MeshMessage(
            id: UUID(),
            payload: payload,
            sourceNode: "LOCAL",
            destinationNode: destination,
            timestamp: Date(),
            direction: .outgoing,
            hopCount: 1
        )
        recentMessages.insert(msg, at: 0)
        if recentMessages.count > 50 { recentMessages.removeLast() }
    }

    private func loadMockData() {
        connectedNodes = [
            LoRaNode(name: "NODE-001", rssi: -72, snr: 8.5, frequency: "915 MHz (Half)", batteryLevel: 85, isRelay: true),
            LoRaNode(name: "NODE-002", rssi: -85, snr: 4.2, frequency: "915 MHz (Half)", batteryLevel: 62, isRelay: false),
            LoRaNode(name: "NODE-003", rssi: -68, snr: 11.1, frequency: "915 MHz (Half)", batteryLevel: 94, isRelay: true),
        ]
    }
}

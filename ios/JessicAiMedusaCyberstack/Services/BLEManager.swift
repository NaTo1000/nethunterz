import Foundation
import CoreBluetooth
import Combine

@MainActor
final class BLEManager: NSObject, ObservableObject {
    static let shared = BLEManager()

    @Published var discoveredDevices: [BLEDevice] = []
    @Published var nrfModules: [BLEDevice] = []
    @Published var flipperDevice: BLEDevice?
    @Published var centralState: CBManagerState = .unknown

    private var centralManager: CBCentralManager!
    private var peripherals: [CBPeripheral] = []

    private override init() {
        super.init()
        centralManager = CBCentralManager(delegate: nil, queue: .main)
    }

    func startScanning() {
        guard centralState == .poweredOn else { return }
        centralManager.scanForPeripherals(withServices: nil, options: [CBCentralManagerScanOptionAllowDuplicatesKey: false])
    }

    func stopScanning() {
        centralManager.stopScan()
    }

    func connect(_ device: BLEDevice) {
        if let peripheral = peripherals.first(where: { $0.identifier == device.identifier }) {
            centralManager.connect(peripheral, options: nil)
        }
    }

    func disconnect(_ device: BLEDevice) {
        if let peripheral = peripherals.first(where: { $0.identifier == device.identifier }) {
            centralManager.cancelPeripheralConnection(peripheral)
        }
    }

    func performOTAUpdate(_ device: BLEDevice, progress: @escaping (Double) -> Void) async {
        for i in 1...10 {
            try? await Task.sleep(nanoseconds: 300_000_000)
            progress(Double(i) / 10.0)
        }
    }

    func sendLoRaConfigToFlipper(_ device: BLEDevice) async { }
    func syncGeofenceToFlipper(_ device: BLEDevice) async { }
    func requestFlipperDiagnostics(_ device: BLEDevice) async { }
}

extension CBManagerState {
    var description: String {
        switch self {
        case .poweredOn: return "Powered On"
        case .poweredOff: return "Powered Off"
        case .unauthorized: return "Unauthorized"
        case .unsupported: return "Unsupported"
        case .resetting: return "Resetting"
        default: return "Unknown"
        }
    }
}

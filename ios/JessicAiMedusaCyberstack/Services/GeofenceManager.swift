import Foundation
import CoreLocation
import Combine

@MainActor
final class GeofenceManager: NSObject, ObservableObject {
    static let shared = GeofenceManager()

    @Published var activeZones: [GeofenceZone] = []
    @Published var recentViolations: [GeofenceViolation] = []
    @Published var isMonitoring: Bool = false

    private var locationManager: CLLocationManager!

    private override init() {
        super.init()
        locationManager = CLLocationManager()
        locationManager.delegate = nil
        locationManager.requestAlwaysAuthorization()
        loadMockData()
    }

    func addZone(name: String, radius: Double, attackMirror: Bool) {
        let zone = GeofenceZone(
            name: name,
            center: locationManager.location?.coordinate ??
                CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194),
            radius: radius,
            attackMirrorEnabled: attackMirror
        )
        activeZones.append(zone)
        startMonitoring(zone)
    }

    func runDefensiveResponse() {
        for i in activeZones.indices where activeZones[i].status == .breach {
            activeZones[i].status = .warning
        }
    }

    func triggerManualResponse(for violation: GeofenceViolation) {
        if let idx = recentViolations.firstIndex(where: { $0.id == violation.id }) {
            recentViolations[idx].isResolved = true
        }
    }

    private func startMonitoring(_ zone: GeofenceZone) {
        let region = CLCircularRegion(
            center: zone.center,
            radius: zone.radius,
            identifier: zone.id.uuidString
        )
        region.notifyOnEntry = true
        region.notifyOnExit = true
        locationManager.startMonitoring(for: region)
        isMonitoring = true
    }

    private func loadMockData() {
        activeZones = [
            GeofenceZone(
                name: "HQ Perimeter",
                center: CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194),
                radius: 200,
                status: .safe,
                attackMirrorEnabled: true
            ),
            GeofenceZone(
                name: "Node Cluster Alpha",
                center: CLLocationCoordinate2D(latitude: 37.78, longitude: -122.41),
                radius: 500,
                status: .warning,
                attackMirrorEnabled: true
            ),
        ]
    }
}

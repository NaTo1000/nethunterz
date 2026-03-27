import Foundation
import CoreLocation
import SwiftUI

struct GeofenceZone: Identifiable, Codable {
    let id: UUID
    var name: String
    var center: CLLocationCoordinate2D
    var radius: Double
    var status: ZoneStatus
    var attackMirrorEnabled: Bool
    var trackedDevices: Int
    var createdAt: Date

    enum ZoneStatus: String, Codable {
        case safe = "Safe"
        case warning = "Warning"
        case breach = "Breach"
    }

    var statusColor: Color {
        switch status {
        case .safe: return .green
        case .warning: return .yellow
        case .breach: return .red
        }
    }

    enum CodingKeys: String, CodingKey {
        case id, name, radius, status, attackMirrorEnabled, trackedDevices, createdAt
        case latitude, longitude
    }

    init(id: UUID = UUID(), name: String, center: CLLocationCoordinate2D,
         radius: Double, status: ZoneStatus = .safe,
         attackMirrorEnabled: Bool = true, trackedDevices: Int = 0,
         createdAt: Date = Date()) {
        self.id = id
        self.name = name
        self.center = center
        self.radius = radius
        self.status = status
        self.attackMirrorEnabled = attackMirrorEnabled
        self.trackedDevices = trackedDevices
        self.createdAt = createdAt
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        radius = try c.decode(Double.self, forKey: .radius)
        status = try c.decode(ZoneStatus.self, forKey: .status)
        attackMirrorEnabled = try c.decode(Bool.self, forKey: .attackMirrorEnabled)
        trackedDevices = try c.decode(Int.self, forKey: .trackedDevices)
        createdAt = try c.decode(Date.self, forKey: .createdAt)
        let lat = try c.decode(Double.self, forKey: .latitude)
        let lon = try c.decode(Double.self, forKey: .longitude)
        center = CLLocationCoordinate2D(latitude: lat, longitude: lon)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id, forKey: .id)
        try c.encode(name, forKey: .name)
        try c.encode(radius, forKey: .radius)
        try c.encode(status, forKey: .status)
        try c.encode(attackMirrorEnabled, forKey: .attackMirrorEnabled)
        try c.encode(trackedDevices, forKey: .trackedDevices)
        try c.encode(createdAt, forKey: .createdAt)
        try c.encode(center.latitude, forKey: .latitude)
        try c.encode(center.longitude, forKey: .longitude)
    }
}

struct GeofenceViolation: Identifiable, Codable {
    let id: UUID
    var zoneName: String
    var description: String
    var timestamp: Date
    var deviceIdentifier: String
    var responseAction: String
    var violationType: ViolationType
    var isResolved: Bool

    enum ViolationType: String, Codable {
        case entry = "Unauthorized Entry"
        case exit = "Unauthorized Exit"
        case signal = "Anomalous Signal"
        case jamming = "Jamming Attempt"
    }
}

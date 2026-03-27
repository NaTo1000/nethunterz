import Foundation
import CoreLocation

struct LoRaNode: Identifiable, Codable {
    let id: UUID
    var name: String
    var rssi: Double
    var snr: Double
    var frequency: String
    var firmwareVersion: String
    var batteryLevel: Int
    var isRelay: Bool
    var lastSeen: Date
    var messagesRelayed: Int
    var uptimeSeconds: TimeInterval
    var coordinate: CLLocationCoordinate2D?

    var shortId: String { name.prefix(4).description }

    var formattedUptime: String {
        let hours = Int(uptimeSeconds) / 3600
        let minutes = (Int(uptimeSeconds) % 3600) / 60
        return "\(hours)h \(minutes)m"
    }

    enum CodingKeys: String, CodingKey {
        case id, name, rssi, snr, frequency, firmwareVersion, batteryLevel
        case isRelay, lastSeen, messagesRelayed, uptimeSeconds
        case latitude, longitude
    }

    init(id: UUID = UUID(), name: String, rssi: Double, snr: Double,
         frequency: String = "915 MHz", firmwareVersion: String = "1.0.0",
         batteryLevel: Int = 100, isRelay: Bool = false,
         lastSeen: Date = Date(), messagesRelayed: Int = 0,
         uptimeSeconds: TimeInterval = 0, coordinate: CLLocationCoordinate2D? = nil) {
        self.id = id
        self.name = name
        self.rssi = rssi
        self.snr = snr
        self.frequency = frequency
        self.firmwareVersion = firmwareVersion
        self.batteryLevel = batteryLevel
        self.isRelay = isRelay
        self.lastSeen = lastSeen
        self.messagesRelayed = messagesRelayed
        self.uptimeSeconds = uptimeSeconds
        self.coordinate = coordinate
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        rssi = try c.decode(Double.self, forKey: .rssi)
        snr = try c.decode(Double.self, forKey: .snr)
        frequency = try c.decode(String.self, forKey: .frequency)
        firmwareVersion = try c.decode(String.self, forKey: .firmwareVersion)
        batteryLevel = try c.decode(Int.self, forKey: .batteryLevel)
        isRelay = try c.decode(Bool.self, forKey: .isRelay)
        lastSeen = try c.decode(Date.self, forKey: .lastSeen)
        messagesRelayed = try c.decode(Int.self, forKey: .messagesRelayed)
        uptimeSeconds = try c.decode(TimeInterval.self, forKey: .uptimeSeconds)
        if let lat = try c.decodeIfPresent(Double.self, forKey: .latitude),
           let lon = try c.decodeIfPresent(Double.self, forKey: .longitude) {
            coordinate = CLLocationCoordinate2D(latitude: lat, longitude: lon)
        }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id, forKey: .id)
        try c.encode(name, forKey: .name)
        try c.encode(rssi, forKey: .rssi)
        try c.encode(snr, forKey: .snr)
        try c.encode(frequency, forKey: .frequency)
        try c.encode(firmwareVersion, forKey: .firmwareVersion)
        try c.encode(batteryLevel, forKey: .batteryLevel)
        try c.encode(isRelay, forKey: .isRelay)
        try c.encode(lastSeen, forKey: .lastSeen)
        try c.encode(messagesRelayed, forKey: .messagesRelayed)
        try c.encode(uptimeSeconds, forKey: .uptimeSeconds)
        try c.encodeIfPresent(coordinate?.latitude, forKey: .latitude)
        try c.encodeIfPresent(coordinate?.longitude, forKey: .longitude)
    }
}

struct MeshMessage: Identifiable, Codable {
    let id: UUID
    let payload: String
    let sourceNode: String
    let destinationNode: String
    let timestamp: Date
    let direction: MessageDirection
    var hopCount: Int

    enum MessageDirection: String, Codable { case incoming, outgoing }
}

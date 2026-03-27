import Foundation
import SwiftUI

struct AIDecision: Identifiable, Codable {
    let id: UUID
    var action: String
    var reasoning: String
    var timestamp: Date
    var severity: Severity
    var category: Category
    var outcome: Outcome
    var actions: [String]
    var confidenceScore: Double

    enum Severity: String, Codable {
        case low = "Low"
        case medium = "Medium"
        case high = "High"
        case critical = "Critical"

        var color: Color {
            switch self {
            case .low: return .green
            case .medium: return .yellow
            case .high: return .orange
            case .critical: return .red
            }
        }
    }

    enum Category: String, Codable {
        case meshOptimization = "Mesh"
        case security = "Security"
        case firmware = "Firmware"
        case geofence = "Geofence"
        case error = "Error"

        var icon: String {
            switch self {
            case .meshOptimization: return "antenna.radiowaves.left.and.right"
            case .security: return "shield.lefthalf.filled"
            case .firmware: return "memorychip"
            case .geofence: return "location.circle"
            case .error: return "exclamationmark.triangle"
            }
        }
    }

    enum Outcome: String, Codable {
        case pending = "Pending"
        case success = "Success"
        case failed = "Failed"
        case mitigated = "Mitigated"

        var color: Color {
            switch self {
            case .pending: return .yellow
            case .success: return .green
            case .failed: return .red
            case .mitigated: return .orange
            }
        }
    }
}

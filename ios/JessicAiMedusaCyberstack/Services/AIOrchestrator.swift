import Foundation
import SwiftUI
import Combine

@MainActor
final class AIOrchestrator: ObservableObject {
    static let shared = AIOrchestrator()

    @Published var recentDecisions: [AIDecision] = []
    @Published var status: AIStatus = .active
    @Published var confidenceScore: Double = 0.94
    @Published var decisionsToday: Int = 0
    @Published var threatsBlocked: Int = 0
    @Published var modelVersion: String = "JessicAi-1.0"

    enum AIStatus: String {
        case active = "Active"
        case learning = "Learning"
        case standby = "Standby"

        var color: Color {
            switch self {
            case .active: return .green
            case .learning: return .yellow
            case .standby: return .gray
            }
        }
    }

    private init() { loadMockDecisions() }

    func executeCommand(_ command: String) async {
        let decision = AIDecision(
            id: UUID(),
            action: "Execute: \(command)",
            reasoning: "User-initiated command processed through JessicAi reasoning engine.",
            timestamp: Date(),
            severity: .medium,
            category: .meshOptimization,
            outcome: .success,
            actions: ["Validated command syntax", "Applied to mesh network", "Logged to audit trail"],
            confidenceScore: 0.91
        )
        recentDecisions.insert(decision, at: 0)
        decisionsToday += 1
    }

    private func loadMockDecisions() {
        recentDecisions = [
            AIDecision(
                id: UUID(),
                action: "Auto-adjusted LoRa spreading factor",
                reasoning: "Signal degradation detected on NODE-002. Increased SF from 9 to 11 to improve range.",
                timestamp: Date().addingTimeInterval(-120),
                severity: .medium,
                category: .meshOptimization,
                outcome: .success,
                actions: ["Detected SNR drop below threshold", "Calculated optimal SF", "Applied SF11 to NODE-002"],
                confidenceScore: 0.95
            ),
            AIDecision(
                id: UUID(),
                action: "Geofence breach mitigated",
                reasoning: "Unknown device detected entering HQ perimeter. Attack mirror system activated.",
                timestamp: Date().addingTimeInterval(-600),
                severity: .high,
                category: .security,
                outcome: .mitigated,
                actions: ["Detected unauthorized entry", "Activated mirror system", "Alerted operator"],
                confidenceScore: 0.88
            ),
            AIDecision(
                id: UUID(),
                action: "ESP32 firmware update queued",
                reasoning: "New firmware v1.2.3 available. Scheduled for low-traffic window.",
                timestamp: Date().addingTimeInterval(-3600),
                severity: .low,
                category: .firmware,
                outcome: .pending,
                actions: ["Checked update server", "Verified firmware signature", "Queued installation"],
                confidenceScore: 0.99
            ),
        ]
        decisionsToday = 14
        threatsBlocked = 3
    }
}

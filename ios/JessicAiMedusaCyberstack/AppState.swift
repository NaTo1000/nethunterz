import Foundation
import Combine
import LocalAuthentication

@MainActor
final class AppState: ObservableObject {
    @Published var isAuthenticated = false
    @Published var colorScheme: AppColorScheme = .dark
    @Published var activeAlerts: [SystemAlert] = []
    @Published var connectionStatus: ConnectionStatus = .disconnected

    func authenticate() async {
        let context = LAContext()
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            // Fallback: allow access in simulator / devices without biometrics
            isAuthenticated = true
            return
        }
        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthenticationWithBiometrics,
                localizedReason: "Authenticate to access JessicAi Medusa Cyberstack"
            )
            isAuthenticated = success
        } catch {
            isAuthenticated = false
        }
    }

    func postAlert(_ alert: SystemAlert) {
        activeAlerts.append(alert)
        Task {
            try? await Task.sleep(nanoseconds: 5_000_000_000)
            activeAlerts.removeAll { $0.id == alert.id }
        }
    }
}

enum AppColorScheme { case dark, light }

enum ConnectionStatus: String {
    case connected = "Connected"
    case disconnected = "Disconnected"
    case scanning = "Scanning"
}

struct SystemAlert: Identifiable {
    let id = UUID()
    let title: String
    let message: String
    let severity: AlertSeverity
    let timestamp: Date

    enum AlertSeverity { case info, warning, critical }
}

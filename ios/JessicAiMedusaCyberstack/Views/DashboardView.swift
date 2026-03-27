import SwiftUI

struct DashboardView: View {
    @StateObject private var loraManager = LoRaManager.shared
    @StateObject private var bleManager = BLEManager.shared
    @StateObject private var aiOrchestrator = AIOrchestrator.shared
    @EnvironmentObject var appState: AppState

    var body: some View {
        NavigationView {
            ScrollView {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                    DashboardCard(
                        title: "LoRa Mesh",
                        value: "\(loraManager.connectedNodes.count)",
                        subtitle: "Active Nodes",
                        icon: "antenna.radiowaves.left.and.right",
                        color: .cyan,
                        trend: loraManager.signalStrength
                    )

                    DashboardCard(
                        title: "BLE Devices",
                        value: "\(bleManager.discoveredDevices.count)",
                        subtitle: "Connected",
                        icon: "dot.radiowaves.left.and.right",
                        color: .blue,
                        trend: nil
                    )

                    DashboardCard(
                        title: "AI Decisions",
                        value: "\(aiOrchestrator.decisionsToday)",
                        subtitle: "Today",
                        icon: "brain.head.profile",
                        color: .purple,
                        trend: nil
                    )

                    DashboardCard(
                        title: "Threats",
                        value: "\(aiOrchestrator.threatsBlocked)",
                        subtitle: "Blocked",
                        icon: "shield.lefthalf.filled",
                        color: .green,
                        trend: nil
                    )
                }
                .padding(.horizontal)

                VStack(alignment: .leading, spacing: 12) {
                    Text("Signal Strength")
                        .font(.headline)
                        .foregroundColor(.white)

                    SignalStrengthView(nodes: loraManager.connectedNodes)
                }
                .padding()
                .background(Color.white.opacity(0.05))
                .cornerRadius(16)
                .padding(.horizontal)

                VStack(alignment: .leading, spacing: 12) {
                    Text("Recent AI Decisions")
                        .font(.headline)
                        .foregroundColor(.white)

                    ForEach(aiOrchestrator.recentDecisions.prefix(3)) { decision in
                        AIDecisionRowView(decision: decision)
                    }
                }
                .padding()
                .background(Color.white.opacity(0.05))
                .cornerRadius(16)
                .padding(.horizontal)

                ESP32StatusWidget()
                    .padding(.horizontal)

                Spacer(minLength: 20)
            }
            .background(
                LinearGradient(
                    colors: [Color.black, Color(red: 0.03, green: 0.03, blue: 0.12)],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .ignoresSafeArea()
            )
            .navigationTitle("Dashboard")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    StatusIndicator(status: appState.connectionStatus)
                }
            }
        }
    }
}

struct DashboardCard: View {
    let title: String
    let value: String
    let subtitle: String
    let icon: String
    let color: Color
    let trend: Double?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundColor(color)
                Spacer()
                if let trend = trend {
                    Image(systemName: trend >= 0 ? "arrow.up.right" : "arrow.down.right")
                        .font(.caption)
                        .foregroundColor(trend >= 0 ? .green : .red)
                }
            }

            Text(value)
                .font(.system(size: 32, weight: .bold, design: .rounded))
                .foregroundColor(.white)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption)
                    .foregroundColor(.gray)
                Text(subtitle)
                    .font(.caption2)
                    .foregroundColor(color.opacity(0.8))
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.white.opacity(0.05))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .strokeBorder(color.opacity(0.3), lineWidth: 1)
                )
        )
    }
}

struct SignalStrengthView: View {
    let nodes: [LoRaNode]

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            ForEach(nodes.prefix(8)) { node in
                VStack(spacing: 4) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(
                            LinearGradient(
                                colors: [signalColor(node.rssi).opacity(0.8), signalColor(node.rssi)],
                                startPoint: .bottom,
                                endPoint: .top
                            )
                        )
                        .frame(width: 24, height: max(4, CGFloat((node.rssi + 120) / 120) * 60))
                    Text(node.shortId)
                        .font(.system(size: 8, design: .monospaced))
                        .foregroundColor(.gray)
                }
            }
            if nodes.isEmpty {
                Text("No nodes connected")
                    .font(.caption)
                    .foregroundColor(.gray)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 20)
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: 80)
    }

    private func signalColor(_ rssi: Double) -> Color {
        if rssi > -70 { return .green }
        if rssi > -90 { return .yellow }
        return .red
    }
}

struct AIDecisionRowView: View {
    let decision: AIDecision

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(decision.severity.color)
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 2) {
                Text(decision.action)
                    .font(.caption)
                    .foregroundColor(.white)
                Text(decision.reasoning)
                    .font(.caption2)
                    .foregroundColor(.gray)
                    .lineLimit(1)
            }

            Spacer()

            Text(decision.timestamp, style: .relative)
                .font(.caption2)
                .foregroundColor(.gray)
        }
        .padding(.vertical, 4)
    }
}

struct ESP32StatusWidget: View {
    @StateObject private var firmwareService = ESP32FirmwareService.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "memorychip")
                    .foregroundColor(.orange)
                Text("ESP32 Firmware")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
                Text(firmwareService.currentVersion)
                    .font(.caption)
                    .foregroundColor(.orange)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.orange.opacity(0.1))
                    .cornerRadius(8)
            }

            if firmwareService.updateAvailable {
                Button("Update Available – Tap to Install") {
                    Task { await firmwareService.installUpdate() }
                }
                .font(.caption)
                .foregroundColor(.black)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(Color.orange)
                .cornerRadius(10)
            } else {
                HStack {
                    Image(systemName: "checkmark.seal.fill")
                        .foregroundColor(.green)
                    Text("Firmware up to date")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(16)
    }
}

struct StatusIndicator: View {
    let status: ConnectionStatus

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(status == .connected ? Color.green : status == .scanning ? Color.yellow : Color.red)
                .frame(width: 8, height: 8)
                .shadow(color: status == .connected ? .green : .clear, radius: 4)
            Text(status.rawValue)
                .font(.caption2)
                .foregroundColor(.gray)
        }
    }
}

struct AlertBannerView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        VStack {
            ForEach(appState.activeAlerts) { alert in
                HStack(spacing: 10) {
                    Image(systemName: alertIcon(alert.severity))
                        .foregroundColor(alertColor(alert.severity))
                    VStack(alignment: .leading, spacing: 2) {
                        Text(alert.title).font(.caption).fontWeight(.bold).foregroundColor(.white)
                        Text(alert.message).font(.caption2).foregroundColor(.gray)
                    }
                    Spacer()
                }
                .padding(10)
                .background(Color.black.opacity(0.85))
                .cornerRadius(12)
                .padding(.horizontal)
                .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .animation(.spring(), value: appState.activeAlerts.count)
    }

    private func alertIcon(_ severity: SystemAlert.AlertSeverity) -> String {
        switch severity {
        case .info: return "info.circle.fill"
        case .warning: return "exclamationmark.triangle.fill"
        case .critical: return "xmark.octagon.fill"
        }
    }

    private func alertColor(_ severity: SystemAlert.AlertSeverity) -> Color {
        switch severity {
        case .info: return .blue
        case .warning: return .yellow
        case .critical: return .red
        }
    }
}

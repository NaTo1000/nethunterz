import SwiftUI
import MapKit

struct LoRaTelemetryView: View {
    @StateObject private var loraManager = LoRaManager.shared
    @State private var selectedNode: LoRaNode?
    @State private var showingFrequencySheet = false
    @State private var mapRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194),
        span: MKCoordinateSpan(latitudeDelta: 0.05, longitudeDelta: 0.05)
    )

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        MeshStatPill(title: "Nodes", value: "\(loraManager.connectedNodes.count)", icon: "point.3.connected.trianglepath.dotted", color: .cyan)
                        MeshStatPill(title: "Frequency", value: loraManager.currentFrequency, icon: "waveform.path.ecg", color: .blue)
                        MeshStatPill(title: "Hop Count", value: "\(loraManager.maxHopCount)", icon: "arrow.triangle.branch", color: .purple)
                        MeshStatPill(title: "TX Power", value: "\(loraManager.txPower) dBm", icon: "bolt.fill", color: .orange)
                        MeshStatPill(title: "SF", value: "SF\(loraManager.spreadingFactor)", icon: "chart.bar.fill", color: .green)
                    }
                    .padding(.horizontal)
                }
                .padding(.vertical, 8)
                .background(Color.black)

                List {
                    Section {
                        ForEach(loraManager.connectedNodes) { node in
                            LoRaNodeRow(node: node, isSelected: selectedNode?.id == node.id)
                                .contentShape(Rectangle())
                                .onTapGesture { selectedNode = node }
                                .listRowBackground(Color.white.opacity(0.04))
                        }
                    } header: {
                        Text("MESH NODES")
                            .font(.caption)
                            .foregroundColor(.cyan)
                            .tracking(2)
                    }

                    if let node = selectedNode {
                        Section {
                            NodeDetailView(node: node)
                                .listRowBackground(Color.cyan.opacity(0.08))
                        } header: {
                            Text("NODE DETAILS")
                                .font(.caption)
                                .foregroundColor(.cyan)
                                .tracking(2)
                        }
                    }

                    Section {
                        ForEach(loraManager.recentMessages.prefix(10)) { msg in
                            MessageRow(message: msg)
                                .listRowBackground(Color.white.opacity(0.03))
                        }
                    } header: {
                        Text("RECENT MESSAGES")
                            .font(.caption)
                            .foregroundColor(.cyan)
                            .tracking(2)
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
                .background(Color(red: 0.03, green: 0.03, blue: 0.12))
            }
            .background(Color.black.ignoresSafeArea())
            .navigationTitle("LoRa Telemetry")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    HStack(spacing: 16) {
                        Button {
                            Task { await loraManager.startMeshScan() }
                        } label: {
                            Image(systemName: "radar")
                                .foregroundColor(.cyan)
                        }
                        Button { showingFrequencySheet = true } label: {
                            Image(systemName: "waveform.path.ecg.rectangle")
                                .foregroundColor(.cyan)
                        }
                    }
                }
            }
            .sheet(isPresented: $showingFrequencySheet) {
                FrequencyConfigSheet(manager: loraManager)
            }
        }
    }
}

struct MeshStatPill: View {
    let title: String
    let value: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundColor(color)
            Text(value)
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.white)
                .fontWeight(.semibold)
            Text(title)
                .font(.system(size: 9))
                .foregroundColor(.gray)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(color.opacity(0.1))
        .cornerRadius(10)
    }
}

struct LoRaNodeRow: View {
    let node: LoRaNode
    let isSelected: Bool

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                Circle()
                    .fill(signalColor(node.rssi).opacity(0.15))
                    .frame(width: 40, height: 40)
                Image(systemName: "antenna.radiowaves.left.and.right")
                    .foregroundColor(signalColor(node.rssi))
                    .font(.system(size: 16))
            }

            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(node.name)
                        .font(.system(.subheadline, design: .monospaced))
                        .foregroundColor(.white)
                    if node.isRelay {
                        Image(systemName: "arrow.triangle.2.circlepath")
                            .font(.caption2)
                            .foregroundColor(.purple)
                    }
                }
                Text("RSSI: \(Int(node.rssi)) dBm  ·  SNR: \(String(format: "%.1f", node.snr)) dB")
                    .font(.caption2)
                    .foregroundColor(.gray)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 3) {
                Text(node.lastSeen, style: .relative)
                    .font(.caption2)
                    .foregroundColor(.gray)
                Text(node.frequency)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.cyan.opacity(0.8))
            }
        }
        .padding(.vertical, 2)
        .background(isSelected ? Color.cyan.opacity(0.08) : Color.clear)
        .cornerRadius(8)
    }

    private func signalColor(_ rssi: Double) -> Color {
        if rssi > -70 { return .green }
        if rssi > -90 { return .yellow }
        return .red
    }
}

struct NodeDetailView: View {
    let node: LoRaNode

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            InfoRow(label: "Node ID", value: node.id.uuidString.prefix(8).description)
            InfoRow(label: "Firmware", value: node.firmwareVersion)
            InfoRow(label: "Battery", value: "\(node.batteryLevel)%")
            InfoRow(label: "Uptime", value: node.formattedUptime)
            InfoRow(label: "Messages Relayed", value: "\(node.messagesRelayed)")
            InfoRow(label: "Location", value: node.coordinate.map {
                String(format: "%.4f, %.4f", $0.latitude, $0.longitude)
            } ?? "Unknown")
        }
    }
}

struct InfoRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label)
                .font(.caption)
                .foregroundColor(.gray)
            Spacer()
            Text(value)
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.white)
        }
    }
}

struct MessageRow: View {
    let message: MeshMessage

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: message.direction == .incoming ? "arrow.down.left" : "arrow.up.right")
                .font(.caption)
                .foregroundColor(message.direction == .incoming ? .cyan : .orange)
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                Text(message.payload)
                    .font(.caption)
                    .foregroundColor(.white)
                    .lineLimit(1)
                Text("\(message.sourceNode)  →  \(message.destinationNode)")
                    .font(.caption2)
                    .foregroundColor(.gray)
            }

            Spacer()

            Text(message.timestamp, style: .time)
                .font(.caption2)
                .foregroundColor(.gray)
        }
        .padding(.vertical, 2)
    }
}

struct FrequencyConfigSheet: View {
    @ObservedObject var manager: LoRaManager
    @Environment(\.dismiss) private var dismiss
    let frequencies = ["433 MHz", "868 MHz", "915 MHz (Half)", "433 MHz (Half)"]

    var body: some View {
        NavigationView {
            Form {
                Section("Frequency Band") {
                    ForEach(frequencies, id: \.self) { freq in
                        HStack {
                            Text(freq)
                            Spacer()
                            if manager.currentFrequency == freq {
                                Image(systemName: "checkmark")
                                    .foregroundColor(.cyan)
                            }
                        }
                        .contentShape(Rectangle())
                        .onTapGesture { manager.currentFrequency = freq }
                    }
                }

                Section("Spreading Factor") {
                    Stepper("SF\(manager.spreadingFactor)", value: $manager.spreadingFactor, in: 7...12)
                }

                Section("TX Power") {
                    Stepper("\(manager.txPower) dBm", value: $manager.txPower, in: 2...20)
                }

                Section("Seek & Find") {
                    Toggle("Enable Beacon Mode", isOn: $manager.beaconModeEnabled)
                    if manager.beaconModeEnabled {
                        Text("Broadcasting beacon every 30s to assist node discovery")
                            .font(.caption)
                            .foregroundColor(.gray)
                    }
                }
            }
            .navigationTitle("LoRa Configuration")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

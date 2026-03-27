import SwiftUI

struct AIOrchestrationView: View {
    @StateObject private var aiOrchestrator = AIOrchestrator.shared
    @State private var commandInput = ""
    @State private var showingQuantumPanel = false

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                HStack(spacing: 16) {
                    ZStack {
                        Circle()
                            .fill(
                                RadialGradient(
                                    colors: [.purple.opacity(0.8), .purple.opacity(0.1)],
                                    center: .center,
                                    startRadius: 5,
                                    endRadius: 25
                                )
                            )
                            .frame(width: 50, height: 50)
                        Image(systemName: "brain.head.profile")
                            .font(.title2)
                            .foregroundColor(.purple)
                    }
                    .shadow(color: .purple.opacity(0.5), radius: 10)

                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 8) {
                            Text("JessicAi")
                                .font(.headline)
                                .foregroundColor(.white)
                            StatusBadge(
                                text: aiOrchestrator.status.rawValue,
                                color: aiOrchestrator.status.color
                            )
                        }
                        Text("Confidence: \(Int(aiOrchestrator.confidenceScore * 100))%  ·  Model: \(aiOrchestrator.modelVersion)")
                            .font(.caption)
                            .foregroundColor(.gray)
                    }

                    Spacer()

                    Button {
                        showingQuantumPanel = true
                    } label: {
                        VStack(spacing: 2) {
                            Image(systemName: "atom")
                                .foregroundColor(.cyan)
                            Text("Quantum")
                                .font(.caption2)
                                .foregroundColor(.cyan)
                        }
                    }
                }
                .padding()
                .background(Color.purple.opacity(0.08))

                ScrollView {
                    LazyVStack(spacing: 1) {
                        ForEach(aiOrchestrator.recentDecisions) { decision in
                            AIDecisionCard(decision: decision)
                        }
                    }
                }

                VStack(spacing: 0) {
                    Divider().background(Color.white.opacity(0.1))
                    HStack(spacing: 12) {
                        Image(systemName: "terminal")
                            .foregroundColor(.purple)
                        TextField("Enter AI command…", text: $commandInput)
                            .font(.system(.body, design: .monospaced))
                            .foregroundColor(.white)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                        Button {
                            guard !commandInput.isEmpty else { return }
                            Task {
                                await aiOrchestrator.executeCommand(commandInput)
                                commandInput = ""
                            }
                        } label: {
                            Image(systemName: "arrow.up.circle.fill")
                                .font(.title2)
                                .foregroundColor(.purple)
                        }
                        .disabled(commandInput.isEmpty)
                    }
                    .padding()
                    .background(Color.black)
                }
            }
            .background(Color(red: 0.03, green: 0.03, blue: 0.12).ignoresSafeArea())
            .navigationTitle("JessicAi Orchestration")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showingQuantumPanel) {
                QuantumCryptoPanel()
            }
        }
    }
}

struct AIDecisionCard: View {
    let decision: AIDecision
    @State private var isExpanded = false

    var body: some View {
        Button { withAnimation(.spring()) { isExpanded.toggle() } } label: {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 12) {
                    Image(systemName: decision.category.icon)
                        .font(.subheadline)
                        .foregroundColor(decision.severity.color)
                        .frame(width: 24)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(decision.action)
                            .font(.subheadline)
                            .foregroundColor(.white)
                            .multilineTextAlignment(.leading)
                        Text(decision.timestamp, style: .relative)
                            .font(.caption2)
                            .foregroundColor(.gray)
                    }

                    Spacer()

                    StatusBadge(text: decision.outcome.rawValue, color: decision.outcome.color)

                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)

                if isExpanded {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(decision.reasoning)
                            .font(.caption)
                            .foregroundColor(.gray)
                            .padding(.horizontal, 16)

                        if !decision.actions.isEmpty {
                            VStack(alignment: .leading, spacing: 4) {
                                ForEach(decision.actions, id: \.self) { action in
                                    HStack(spacing: 6) {
                                        Circle().fill(Color.purple).frame(width: 4, height: 4)
                                        Text(action)
                                            .font(.caption2)
                                            .foregroundColor(.purple.opacity(0.9))
                                    }
                                }
                            }
                            .padding(.horizontal, 16)
                        }
                    }
                    .padding(.bottom, 12)
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
            .background(Color.white.opacity(0.04))
        }
        .buttonStyle(.plain)
    }
}

struct StatusBadge: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption2)
            .foregroundColor(color)
            .padding(.horizontal, 6)
            .padding(.vertical, 3)
            .background(color.opacity(0.12))
            .cornerRadius(6)
    }
}

struct QuantumCryptoPanel: View {
    @StateObject private var quantumService = QuantumCryptoService.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            Form {
                Section("IBM Quantum Cloud") {
                    InfoRow(label: "Backend", value: quantumService.backendName)
                    InfoRow(label: "Qubits", value: "\(quantumService.availableQubits)")
                    InfoRow(label: "Queue Depth", value: "\(quantumService.queueDepth)")
                    InfoRow(label: "Status", value: quantumService.isConnected ? "Online" : "Offline")
                }

                Section("Cryptographic Defense") {
                    InfoRow(label: "Algorithm", value: "AES-256 + QKD")
                    InfoRow(label: "Key Strength", value: "256-bit quantum-enhanced")
                    InfoRow(label: "Last Rotation", value: quantumService.lastKeyRotation.formatted(date: .abbreviated, time: .shortened))
                }

                Section {
                    Button("Rotate Encryption Keys") {
                        Task { await quantumService.rotateKeys() }
                    }
                    .foregroundColor(.cyan)

                    Button("Run Quantum Error Correction") {
                        Task { await quantumService.runErrorCorrection() }
                    }
                    .foregroundColor(.purple)
                }
            }
            .navigationTitle("IBM Quantum")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
    }
}

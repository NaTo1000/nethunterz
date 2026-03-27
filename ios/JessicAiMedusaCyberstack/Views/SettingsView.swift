import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @State private var notificationsEnabled = true
    @State private var backgroundRefresh = true
    @State private var encryptionLevel = 256
    @State private var showingAbout = false

    var body: some View {
        NavigationView {
            Form {
                Section("Appearance") {
                    HStack {
                        Label("Color Scheme", systemImage: "circle.lefthalf.filled")
                        Spacer()
                        Picker("", selection: $appState.colorScheme) {
                            Text("Dark").tag(AppColorScheme.dark)
                            Text("Light").tag(AppColorScheme.light)
                        }
                        .pickerStyle(.segmented)
                        .frame(width: 140)
                    }
                }

                Section("Notifications") {
                    Toggle(isOn: $notificationsEnabled) {
                        Label("Push Notifications", systemImage: "bell.fill")
                    }
                    .tint(.cyan)
                    Toggle(isOn: $backgroundRefresh) {
                        Label("Background Refresh", systemImage: "arrow.clockwise")
                    }
                    .tint(.cyan)
                }

                Section("Security") {
                    HStack {
                        Label("Encryption", systemImage: "lock.shield.fill")
                        Spacer()
                        Text("AES-\(encryptionLevel)")
                            .font(.caption)
                            .foregroundColor(.cyan)
                    }

                    Button {
                        Task { await appState.authenticate() }
                    } label: {
                        Label("Re-Authenticate", systemImage: "faceid")
                    }
                    .foregroundColor(.cyan)

                    Button(role: .destructive) {
                        appState.isAuthenticated = false
                    } label: {
                        Label("Lock App", systemImage: "lock.fill")
                    }
                }

                Section("About") {
                    InfoRow(label: "App Version", value: "1.0.0")
                    InfoRow(label: "Build", value: "2026.03")
                    InfoRow(label: "Stack", value: "NetHunterz v1.0")
                    InfoRow(label: "AI Engine", value: "JessicAi v1.0")
                    Button("View Licenses") { showingAbout = true }
                        .foregroundColor(.cyan)
                }

                Section("Danger Zone") {
                    Button(role: .destructive) {
                        // Reset all settings
                    } label: {
                        Label("Reset Configuration", systemImage: "trash.fill")
                    }
                }
            }
            .navigationTitle("Settings")
        }
        .sheet(isPresented: $showingAbout) {
            AboutView()
        }
    }
}

struct AboutView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    Image(systemName: "shield.lefthalf.filled")
                        .font(.system(size: 60))
                        .foregroundStyle(
                            LinearGradient(colors: [.cyan, .blue], startPoint: .top, endPoint: .bottom)
                        )
                        .padding(.top, 30)

                    Text("JessicAi Medusa Cyberstack")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.white)

                    Text("Version 1.0.0 (2026.03)")
                        .font(.caption)
                        .foregroundColor(.gray)

                    Text("A professional cybersecurity platform combining LoRa mesh networking, BLE device management, AI-driven threat response, and quantum-enhanced cryptography.\n\nPowered by the NetHunterz stack.")
                        .font(.body)
                        .foregroundColor(.gray)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)

                    Spacer()
                }
            }
            .background(Color.black.ignoresSafeArea())
            .navigationTitle("About")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
    }
}

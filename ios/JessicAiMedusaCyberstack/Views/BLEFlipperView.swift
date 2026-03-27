import SwiftUI
import CoreBluetooth

struct BLEFlipperView: View {
    @StateObject private var bleManager = BLEManager.shared
    @State private var showingDeviceDetail: BLEDevice?
    @State private var isScanning = false

    var body: some View {
        NavigationView {
            List {
                Section {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("BLE Radio")
                                .font(.subheadline)
                                .foregroundColor(.white)
                            Text(bleManager.centralState.description)
                                .font(.caption)
                                .foregroundColor(bleManager.centralState == .poweredOn ? .green : .red)
                        }
                        Spacer()
                        if isScanning {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .cyan))
                        }
                    }
                    .listRowBackground(Color.white.opacity(0.05))
                } header: {
                    Text("BLUETOOTH STATUS")
                        .font(.caption).foregroundColor(.cyan).tracking(2)
                }

                Section {
                    if let flipper = bleManager.flipperDevice {
                        FlipperZeroRow(device: flipper)
                            .onTapGesture { showingDeviceDetail = flipper }
                    } else {
                        Text("No Flipper Zero detected")
                            .font(.caption)
                            .foregroundColor(.gray)
                    }
                } header: {
                    Text("FLIPPER ZERO")
                        .font(.caption).foregroundColor(.cyan).tracking(2)
                }
                .listRowBackground(Color.white.opacity(0.04))

                Section {
                    ForEach(bleManager.nrfModules) { device in
                        BLEDeviceRow(device: device)
                            .onTapGesture { showingDeviceDetail = device }
                            .listRowBackground(Color.white.opacity(0.04))
                    }
                    if bleManager.nrfModules.isEmpty {
                        Text("No NRF modules detected")
                            .font(.caption)
                            .foregroundColor(.gray)
                            .listRowBackground(Color.white.opacity(0.03))
                    }
                } header: {
                    Text("NRF MODULES / PINGEQUA")
                        .font(.caption).foregroundColor(.cyan).tracking(2)
                }

                Section {
                    ForEach(bleManager.discoveredDevices) { device in
                        BLEDeviceRow(device: device)
                            .onTapGesture { showingDeviceDetail = device }
                            .listRowBackground(Color.white.opacity(0.03))
                    }
                } header: {
                    Text("NEARBY DEVICES (\(bleManager.discoveredDevices.count))")
                        .font(.caption).foregroundColor(.cyan).tracking(2)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
            .background(Color(red: 0.03, green: 0.03, blue: 0.12).ignoresSafeArea())
            .navigationTitle("BLE & Flipper Zero")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        isScanning.toggle()
                        if isScanning {
                            bleManager.startScanning()
                            Task {
                                try? await Task.sleep(nanoseconds: 10_000_000_000)
                                bleManager.stopScanning()
                                isScanning = false
                            }
                        } else {
                            bleManager.stopScanning()
                        }
                    } label: {
                        Image(systemName: isScanning ? "stop.circle.fill" : "magnifyingglass")
                            .foregroundColor(.cyan)
                    }
                }
            }
            .sheet(item: $showingDeviceDetail) { device in
                BLEDeviceDetailView(device: device, manager: bleManager)
            }
        }
    }
}

struct FlipperZeroRow: View {
    let device: BLEDevice

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(Color.orange.opacity(0.15))
                    .frame(width: 44, height: 44)
                Image(systemName: "wand.and.rays")
                    .foregroundColor(.orange)
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(device.name)
                    .font(.subheadline)
                    .foregroundColor(.white)
                HStack(spacing: 8) {
                    Circle()
                        .fill(device.isConnected ? Color.green : Color.gray)
                        .frame(width: 6, height: 6)
                    Text(device.isConnected ? "Connected" : "Available")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }

            Spacer()

            VStack(alignment: .trailing) {
                Text("\(device.rssi) dBm")
                    .font(.caption)
                    .foregroundColor(.orange)
                if device.isConnected {
                    Image(systemName: "checkmark.shield.fill")
                        .font(.caption)
                        .foregroundColor(.green)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

struct BLEDeviceRow: View {
    let device: BLEDevice

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: device.deviceType.icon)
                .font(.title3)
                .foregroundColor(device.deviceType.color)
                .frame(width: 36)

            VStack(alignment: .leading, spacing: 3) {
                Text(device.name.isEmpty ? "Unknown Device" : device.name)
                    .font(.subheadline)
                    .foregroundColor(.white)
                Text(device.identifier.uuidString.prefix(16).description + "...")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.gray)
            }

            Spacer()

            HStack(spacing: 8) {
                Text("\(device.rssi) dBm")
                    .font(.caption)
                    .foregroundColor(.gray)
                Circle()
                    .fill(device.isConnected ? Color.green : Color.gray.opacity(0.5))
                    .frame(width: 8, height: 8)
            }
        }
        .padding(.vertical, 2)
    }
}

struct BLEDeviceDetailView: View {
    let device: BLEDevice
    @ObservedObject var manager: BLEManager
    @Environment(\.dismiss) private var dismiss
    @State private var firmwareUpdateProgress: Double?

    var body: some View {
        NavigationView {
            Form {
                Section("Device Info") {
                    InfoRow(label: "Name", value: device.name)
                    InfoRow(label: "ID", value: device.identifier.uuidString)
                    InfoRow(label: "RSSI", value: "\(device.rssi) dBm")
                    InfoRow(label: "Type", value: device.deviceType.rawValue)
                    InfoRow(label: "Status", value: device.isConnected ? "Connected" : "Disconnected")
                }

                if device.deviceType == .flipperZero {
                    Section("Flipper Zero Actions") {
                        Button("Send LoRa Config") {
                            Task { await manager.sendLoRaConfigToFlipper(device) }
                        }
                        Button("Sync Geofence Data") {
                            Task { await manager.syncGeofenceToFlipper(device) }
                        }
                        Button("Remote Diagnostics") {
                            Task { await manager.requestFlipperDiagnostics(device) }
                        }
                    }
                }

                Section("Firmware") {
                    if let progress = firmwareUpdateProgress {
                        ProgressView("Updating Firmware…", value: progress, total: 1.0)
                            .progressViewStyle(.linear)
                            .tint(.cyan)
                    } else {
                        Button("OTA Firmware Update") {
                            Task {
                                firmwareUpdateProgress = 0
                                await manager.performOTAUpdate(device) { p in
                                    firmwareUpdateProgress = p
                                }
                                firmwareUpdateProgress = nil
                            }
                        }
                        .foregroundColor(.cyan)
                    }
                }

                Section {
                    Button(device.isConnected ? "Disconnect" : "Connect") {
                        if device.isConnected {
                            manager.disconnect(device)
                        } else {
                            manager.connect(device)
                        }
                    }
                    .foregroundColor(device.isConnected ? .red : .green)
                }
            }
            .navigationTitle(device.name.isEmpty ? "BLE Device" : device.name)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
    }
}

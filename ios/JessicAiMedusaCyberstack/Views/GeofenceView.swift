import SwiftUI
import MapKit
import CoreLocation

struct GeofenceView: View {
    @StateObject private var geofenceManager = GeofenceManager.shared
    @State private var mapRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194),
        span: MKCoordinateSpan(latitudeDelta: 0.1, longitudeDelta: 0.1)
    )
    @State private var showingAddGeofence = false
    @State private var selectedViolation: GeofenceViolation?

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                Map(coordinateRegion: $mapRegion, annotationItems: geofenceManager.activeZones) { zone in
                    MapAnnotation(coordinate: zone.center) {
                        GeofenceAnnotationView(zone: zone)
                    }
                }
                .frame(height: 280)
                .overlay(alignment: .bottomTrailing) {
                    HStack(spacing: 10) {
                        LegendPill(color: .green, label: "Safe")
                        LegendPill(color: .yellow, label: "Warning")
                        LegendPill(color: .red, label: "Breach")
                    }
                    .padding(10)
                    .background(.ultraThinMaterial)
                    .cornerRadius(10)
                    .padding(10)
                }

                List {
                    Section {
                        ForEach(geofenceManager.activeZones) { zone in
                            GeofenceZoneRow(zone: zone)
                                .listRowBackground(Color.white.opacity(0.04))
                        }
                    } header: {
                        HStack {
                            Text("ACTIVE ZONES (\(geofenceManager.activeZones.count))")
                                .font(.caption).foregroundColor(.cyan).tracking(2)
                            Spacer()
                            Button("+ Add") { showingAddGeofence = true }
                                .font(.caption).foregroundColor(.cyan)
                        }
                    }

                    Section {
                        ForEach(geofenceManager.recentViolations.prefix(5)) { violation in
                            GeofenceViolationRow(violation: violation)
                                .onTapGesture { selectedViolation = violation }
                                .listRowBackground(Color.red.opacity(0.05))
                        }
                        if geofenceManager.recentViolations.isEmpty {
                            HStack {
                                Image(systemName: "checkmark.shield.fill")
                                    .foregroundColor(.green)
                                Text("No violations detected")
                                    .font(.caption)
                                    .foregroundColor(.gray)
                            }
                            .listRowBackground(Color.white.opacity(0.03))
                        }
                    } header: {
                        Text("RECENT VIOLATIONS")
                            .font(.caption).foregroundColor(.red).tracking(2)
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
                .background(Color(red: 0.03, green: 0.03, blue: 0.12))
            }
            .background(Color.black.ignoresSafeArea())
            .navigationTitle("Geofencing")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    HStack(spacing: 16) {
                        Button {
                            geofenceManager.runDefensiveResponse()
                        } label: {
                            Image(systemName: "shield.lefthalf.filled.badge.checkmark")
                                .foregroundColor(.orange)
                        }
                        Button { showingAddGeofence = true } label: {
                            Image(systemName: "plus.circle")
                                .foregroundColor(.cyan)
                        }
                    }
                }
            }
            .sheet(isPresented: $showingAddGeofence) {
                AddGeofenceSheet(manager: geofenceManager)
            }
            .sheet(item: $selectedViolation) { violation in
                ViolationDetailView(violation: violation, manager: geofenceManager)
            }
        }
    }
}

struct GeofenceAnnotationView: View {
    let zone: GeofenceZone

    var body: some View {
        ZStack {
            Circle()
                .stroke(zone.statusColor, lineWidth: 2)
                .frame(width: 44, height: 44)
                .opacity(0.7)
            Image(systemName: "location.circle.fill")
                .foregroundColor(zone.statusColor)
                .font(.title3)
        }
    }
}

struct LegendPill: View {
    let color: Color
    let label: String

    var body: some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(label).font(.caption2).foregroundColor(.white)
        }
    }
}

struct GeofenceZoneRow: View {
    let zone: GeofenceZone

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                Circle()
                    .fill(zone.statusColor.opacity(0.15))
                    .frame(width: 40, height: 40)
                Image(systemName: "location.circle")
                    .foregroundColor(zone.statusColor)
            }

            VStack(alignment: .leading, spacing: 3) {
                Text(zone.name)
                    .font(.subheadline)
                    .foregroundColor(.white)
                Text("Radius: \(Int(zone.radius))m  ·  \(zone.trackedDevices) devices")
                    .font(.caption2)
                    .foregroundColor(.gray)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 3) {
                Text(zone.status.rawValue)
                    .font(.caption)
                    .foregroundColor(zone.statusColor)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(zone.statusColor.opacity(0.1))
                    .cornerRadius(6)
                if zone.attackMirrorEnabled {
                    Image(systemName: "shield.fill")
                        .font(.caption2)
                        .foregroundColor(.orange)
                }
            }
        }
        .padding(.vertical, 2)
    }
}

struct GeofenceViolationRow: View {
    let violation: GeofenceViolation

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.red)

            VStack(alignment: .leading, spacing: 2) {
                Text(violation.zoneName)
                    .font(.subheadline)
                    .foregroundColor(.white)
                Text(violation.description)
                    .font(.caption)
                    .foregroundColor(.gray)
                    .lineLimit(1)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                Text(violation.timestamp, style: .relative)
                    .font(.caption2)
                    .foregroundColor(.gray)
                Text(violation.responseAction)
                    .font(.caption2)
                    .foregroundColor(.orange)
            }
        }
        .padding(.vertical, 2)
    }
}

struct AddGeofenceSheet: View {
    @ObservedObject var manager: GeofenceManager
    @Environment(\.dismiss) private var dismiss
    @State private var zoneName = ""
    @State private var radius: Double = 100
    @State private var attackMirrorEnabled = true

    var body: some View {
        NavigationView {
            Form {
                Section("Zone Configuration") {
                    TextField("Zone Name", text: $zoneName)
                    HStack {
                        Text("Radius")
                        Spacer()
                        Text("\(Int(radius))m")
                            .foregroundColor(.cyan)
                    }
                    Slider(value: $radius, in: 50...5000, step: 50)
                        .tint(.cyan)
                }
                Section("Defensive Options") {
                    Toggle("Attack Mirror System", isOn: $attackMirrorEnabled)
                    if attackMirrorEnabled {
                        Text("AI will autonomously mirror and deflect attacks when a breach is detected.")
                            .font(.caption)
                            .foregroundColor(.gray)
                    }
                }
                Section {
                    Button("Create Geofence") {
                        manager.addZone(name: zoneName, radius: radius, attackMirror: attackMirrorEnabled)
                        dismiss()
                    }
                    .foregroundColor(.cyan)
                    .disabled(zoneName.isEmpty)
                }
            }
            .navigationTitle("New Geofence Zone")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

struct ViolationDetailView: View {
    let violation: GeofenceViolation
    @ObservedObject var manager: GeofenceManager
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            Form {
                Section("Violation Details") {
                    InfoRow(label: "Zone", value: violation.zoneName)
                    InfoRow(label: "Time", value: violation.timestamp.formatted())
                    InfoRow(label: "Device", value: violation.deviceIdentifier)
                    InfoRow(label: "Type", value: violation.violationType.rawValue)
                }
                Section("Response") {
                    InfoRow(label: "AI Action", value: violation.responseAction)
                    InfoRow(label: "Status", value: violation.isResolved ? "Resolved" : "Active")
                }
                Section {
                    Button("Trigger Manual Response") {
                        manager.triggerManualResponse(for: violation)
                    }
                    .foregroundColor(.orange)
                }
            }
            .navigationTitle("Violation Details")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
    }
}

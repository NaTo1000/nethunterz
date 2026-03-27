import SwiftUI

struct MainTabView: View {
    @EnvironmentObject var appState: AppState
    @State private var selectedTab: Tab = .dashboard

    enum Tab { case dashboard, lora, ble, geofence, ai, settings }

    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem {
                    Label("Dashboard", systemImage: "gauge.with.dots.needle.bottom.50percent")
                }
                .tag(Tab.dashboard)

            LoRaTelemetryView()
                .tabItem {
                    Label("LoRa", systemImage: "antenna.radiowaves.left.and.right")
                }
                .tag(Tab.lora)

            BLEFlipperView()
                .tabItem {
                    Label("BLE", systemImage: "dot.radiowaves.left.and.right")
                }
                .tag(Tab.ble)

            GeofenceView()
                .tabItem {
                    Label("Geofence", systemImage: "map.fill")
                }
                .tag(Tab.geofence)

            AIOrchestrationView()
                .tabItem {
                    Label("JessicAi", systemImage: "brain.head.profile")
                }
                .tag(Tab.ai)

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.2.fill")
                }
                .tag(Tab.settings)
        }
        .accentColor(.cyan)
        .preferredColorScheme(appState.colorScheme == .dark ? .dark : .light)
        .overlay(alignment: .top) {
            AlertBannerView()
                .environmentObject(appState)
        }
    }
}

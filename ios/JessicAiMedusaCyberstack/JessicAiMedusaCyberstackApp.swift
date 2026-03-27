import SwiftUI

@main
struct JessicAiMedusaCyberstackApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            if appState.isAuthenticated {
                MainTabView()
                    .environmentObject(appState)
            } else {
                AuthView()
                    .environmentObject(appState)
            }
        }
    }
}

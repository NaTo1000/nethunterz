import SwiftUI
import LocalAuthentication

struct AuthView: View {
    @EnvironmentObject var appState: AppState
    @State private var showError = false
    @State private var errorMessage = ""
    @State private var isAuthenticating = false

    var body: some View {
        ZStack {
            LinearGradient(
                gradient: Gradient(colors: [Color.black, Color(red: 0.05, green: 0.05, blue: 0.15)]),
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 40) {
                Spacer()

                VStack(spacing: 16) {
                    Image(systemName: "shield.lefthalf.filled")
                        .font(.system(size: 80))
                        .foregroundStyle(
                            LinearGradient(colors: [.cyan, .blue], startPoint: .top, endPoint: .bottom)
                        )
                        .shadow(color: .cyan.opacity(0.5), radius: 20)

                    Text("JessicAi")
                        .font(.system(size: 42, weight: .bold, design: .rounded))
                        .foregroundStyle(
                            LinearGradient(colors: [.white, .cyan], startPoint: .top, endPoint: .bottom)
                        )

                    Text("Medusa Cyberstack")
                        .font(.system(size: 18, weight: .medium, design: .monospaced))
                        .foregroundColor(.cyan.opacity(0.8))
                        .tracking(4)

                    Text("NetHunterz Security Platform")
                        .font(.caption)
                        .foregroundColor(.gray)
                        .tracking(2)
                }

                Spacer()

                VStack(spacing: 20) {
                    if showError {
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundColor(.red)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }

                    Button {
                        isAuthenticating = true
                        Task {
                            await appState.authenticate()
                            isAuthenticating = false
                        }
                    } label: {
                        HStack(spacing: 12) {
                            Image(systemName: "faceid")
                                .font(.title2)
                            Text("Authenticate")
                                .font(.headline)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(
                            LinearGradient(colors: [.cyan, .blue], startPoint: .leading, endPoint: .trailing)
                        )
                        .foregroundColor(.white)
                        .cornerRadius(14)
                        .shadow(color: .cyan.opacity(0.4), radius: 12)
                    }
                    .disabled(isAuthenticating)
                    .padding(.horizontal, 32)
                }

                Spacer()
                    .frame(height: 40)
            }
        }
    }
}

struct AuthView_Previews: PreviewProvider {
    static var previews: some View {
        AuthView()
            .environmentObject(AppState())
    }
}

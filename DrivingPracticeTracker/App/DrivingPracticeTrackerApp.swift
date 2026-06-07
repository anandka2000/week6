import SwiftUI

@main
struct DrivingPracticeTrackerApp: App {
    @StateObject private var store            = SessionStore.shared
    @StateObject private var detectionManager = DrivingDetectionManager.shared
    @Environment(\.scenePhase) private var scenePhase

    init() {
        // Recover any session that ended while the app was killed
        DrivingDetectionManager.shared.recoverSession()
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
                .environmentObject(detectionManager)
        }
        .onChange(of: scenePhase) { _, phase in
            // Re-run recovery each time the app returns to foreground,
            // in case a drive ended while the app was backgrounded.
            if phase == .active {
                detectionManager.recoverSession()
            }
        }
    }
}

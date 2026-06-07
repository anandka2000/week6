import Foundation
import CoreMotion
import UserNotifications

/// Monitors device motion to detect driving sessions in the background.
/// When a drive ends, fires a local notification prompting the user to log it.
class DrivingDetectionManager: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    static let shared = DrivingDetectionManager()

    // MARK: - Published state
    @Published private(set) var isEnabled: Bool
    @Published private(set) var isDriving: Bool

    // MARK: - Constants
    private let minSessionMinutes  = 5
    private let stopDebounceSeconds: TimeInterval = 3 * 60   // 3 min before confirming drive ended

    // MARK: - Private
    private let motionManager      = CMMotionActivityManager()
    private let notificationCenter = UNUserNotificationCenter.current()
    private var stopCandidateTime: Date?   // when non-automotive activity first seen

    private enum UDKey {
        static let isEnabled  = "detectionEnabled"
        static let isDriving  = "detectionIsDriving"
        static let driveStart = "detectionDriveStart"
        static let pending    = "detectionPendingSession"
    }

    // MARK: - Init
    private override init() {
        isEnabled = UserDefaults.standard.bool(forKey: UDKey.isEnabled)
        isDriving = UserDefaults.standard.bool(forKey: UDKey.isDriving)
        super.init()
        notificationCenter.delegate = self
        registerNotificationCategory()
        if isEnabled { startMonitoring() }
    }

    // MARK: - Enable / disable

    /// Requests Motion + Notification permissions, then starts monitoring. Returns true on success.
    func requestPermissionsAndEnable() async -> Bool {
        guard CMMotionActivityManager.isActivityAvailable() else { return false }
        guard (try? await notificationCenter.requestAuthorization(options: [.alert, .sound])) == true else {
            return false
        }
        await MainActor.run {
            isEnabled = true
            UserDefaults.standard.set(true, forKey: UDKey.isEnabled)
            startMonitoring()
        }
        return true
    }

    func disable() {
        isEnabled = false
        isDriving = false
        stopCandidateTime = nil
        motionManager.stopActivityUpdates()
        UserDefaults.standard.set(false, forKey: UDKey.isEnabled)
        UserDefaults.standard.set(false, forKey: UDKey.isDriving)
    }

    // MARK: - Monitoring

    func startMonitoring() {
        guard CMMotionActivityManager.isActivityAvailable() else { return }
        // Delivered on main queue; also replays any buffered updates since last launch.
        motionManager.startActivityUpdates(to: .main) { [weak self] activity in
            guard let activity, let self else { return }
            self.handleActivity(activity)
        }
    }

    /// Call on app launch / foreground to catch sessions that finished while the app was killed.
    func recoverSession() {
        guard isEnabled,
              UserDefaults.standard.bool(forKey: UDKey.isDriving) else { return }

        let startInterval = UserDefaults.standard.double(forKey: UDKey.driveStart)
        guard startInterval > 0 else { clearDriveState(); return }

        let driveStart = Date(timeIntervalSince1970: startInterval)

        // Query activity history from drive start to now
        motionManager.queryActivityStarting(from: driveStart, to: Date(), to: .main) { [weak self] activities, _ in
            guard let self, let activities else { return }

            // Find the last automotive activity and first sustained non-automotive block
            if let lastAuto = activities.last(where: { $0.automotive }),
               let afterStop = activities.last(where: {
                   !$0.automotive && $0.startDate > lastAuto.startDate
               }),
               afterStop.startDate.timeIntervalSince(lastAuto.startDate) >= self.stopDebounceSeconds {

                let minutes = Int(lastAuto.startDate.timeIntervalSince(driveStart) / 60)
                if minutes >= self.minSessionMinutes {
                    self.firePendingSession(startTime: driveStart, minutes: minutes)
                }
            }
            self.clearDriveState()
        }
    }

    // MARK: - Activity handling

    private func handleActivity(_ activity: CMMotionActivity) {
        guard isEnabled else { return }

        if activity.automotive && activity.confidence != .low {
            // — Driving —
            stopCandidateTime = nil
            if !isDriving {
                isDriving = true
                UserDefaults.standard.set(true, forKey: UDKey.isDriving)
                UserDefaults.standard.set(activity.startDate.timeIntervalSince1970, forKey: UDKey.driveStart)
            }
        } else if !activity.automotive && isDriving {
            // — Possible stop —
            if stopCandidateTime == nil { stopCandidateTime = activity.startDate }
            guard let candidateTime = stopCandidateTime,
                  Date().timeIntervalSince(candidateTime) >= stopDebounceSeconds else { return }
            endSession(stopTime: candidateTime)
        }
    }

    private func endSession(stopTime: Date) {
        let startInterval = UserDefaults.standard.double(forKey: UDKey.driveStart)
        guard startInterval > 0 else { clearDriveState(); return }

        let driveStart = Date(timeIntervalSince1970: startInterval)
        let minutes = Int(stopTime.timeIntervalSince(driveStart) / 60)

        if minutes >= minSessionMinutes {
            firePendingSession(startTime: driveStart, minutes: minutes)
        }
        clearDriveState()
    }

    private func clearDriveState() {
        isDriving = false
        stopCandidateTime = nil
        UserDefaults.standard.set(false, forKey: UDKey.isDriving)
        UserDefaults.standard.removeObject(forKey: UDKey.driveStart)
    }

    // MARK: - Pending session

    struct PendingSession: Codable {
        let startTime: Date
        let durationMinutes: Int
    }

    private func firePendingSession(startTime: Date, minutes: Int) {
        // Persist for LogSessionView to consume
        if let data = try? JSONEncoder().encode(PendingSession(startTime: startTime, durationMinutes: minutes)) {
            UserDefaults.standard.set(data, forKey: UDKey.pending)
        }

        let content = UNMutableNotificationContent()
        content.title = "Driving Session Detected"
        content.body  = "You drove for \(formatMinutes(minutes)). Log it?"
        content.sound = .default
        content.categoryIdentifier = "DRIVING_SESSION"

        let request = UNNotificationRequest(
            identifier: "drive-\(Int(Date().timeIntervalSince1970))",
            content: content,
            trigger: nil   // deliver immediately
        )
        notificationCenter.add(request)
    }

    /// Consumes and returns the pending detected session (call once from LogSessionView.onAppear).
    static func consumePendingSession() -> PendingSession? {
        guard let data = UserDefaults.standard.data(forKey: UDKey.pending),
              let session = try? JSONDecoder().decode(PendingSession.self, from: data) else { return nil }
        UserDefaults.standard.removeObject(forKey: UDKey.pending)
        return session
    }

    // MARK: - Notification category

    private func registerNotificationCategory() {
        let log     = UNNotificationAction(identifier: "LOG_SESSION",     title: "Log Now",  options: .foreground)
        let discard = UNNotificationAction(identifier: "DISCARD_SESSION", title: "Discard",  options: .destructive)
        let cat     = UNNotificationCategory(identifier: "DRIVING_SESSION",
                                             actions: [log, discard],
                                             intentIdentifiers: [])
        notificationCenter.setNotificationCategories([cat])
    }

    // MARK: - UNUserNotificationCenterDelegate

    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        if response.actionIdentifier == "DISCARD_SESSION" {
            UserDefaults.standard.removeObject(forKey: UDKey.pending)
        }
        // LOG_SESSION / default tap: app opens → LogSessionView.onAppear picks it up
        completionHandler()
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }

    // MARK: - Helpers

    private func formatMinutes(_ minutes: Int) -> String {
        let h = minutes / 60, m = minutes % 60
        switch (h, m) {
        case (0, _): return "\(m) min"
        case (_, 0): return "\(h) hr"
        default:     return "\(h) hr \(m) min"
        }
    }
}

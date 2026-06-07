import Foundation
import Combine

/// Central data store for all driving sessions, jurisdiction selection, and requirements profile.
/// Singleton so App Intents can access it without a SwiftUI context.
class SessionStore: ObservableObject {
    static let shared = SessionStore()

    // MARK: - Published properties

    @Published var sessions: [DrivingSession] = []
    @Published var profile: RequirementsProfile = RequirementsProfile.defaultProfile

    // Jurisdiction selection
    @Published var selectedCountry: JurisdictionCountry = .australia
    @Published var selectedRegionId: UUID = RequirementsProfile.australiaRegions[0].id

    // Custom profile — persisted separately; never reset by switching jurisdiction
    @Published var savedCustomProfile: RequirementsProfile = RequirementsProfile.defaultCustomProfile

    // MARK: - File URLs

    private let fm = FileManager.default
    private var docs: URL { fm.urls(for: .documentDirectory, in: .userDomainMask)[0] }
    private var sessionsURL:      URL { docs.appendingPathComponent("sessions.json") }
    private var profileURL:       URL { docs.appendingPathComponent("profile.json") }
    private var jurisdictionURL:  URL { docs.appendingPathComponent("jurisdiction.json") }
    private var customProfileURL: URL { docs.appendingPathComponent("customProfile.json") }

    // MARK: - Init

    private init() {
        loadSessions()
        loadCustomProfile()   // must be before loadJurisdiction
        loadJurisdiction()    // calls applyJurisdiction which may reference savedCustomProfile
    }

    // MARK: - Jurisdiction selection

    func selectCountry(_ country: JurisdictionCountry) {
        selectedCountry = country
        applyJurisdiction()
        saveJurisdiction()
    }

    func selectRegion(_ region: RequirementsProfile) {
        selectedRegionId = region.id
        profile = region
        saveProfile()
        saveJurisdiction()
    }

    /// Updates the custom profile. If Custom is the active country, also updates the live profile.
    func updateCustomProfile(_ updated: RequirementsProfile) {
        savedCustomProfile = updated
        saveCustomProfile()
        if selectedCountry == .custom {
            profile = updated
            saveProfile()
        }
    }

    // MARK: - Computed statistics

    var totalHours: Double    { sessions.reduce(0) { $0 + $1.durationHours } }
    var nightHours: Double    { sessions.filter(\.isNight).reduce(0)   { $0 + $1.durationHours } }
    var highwayHours: Double  { sessions.filter(\.isHighway).reduce(0) { $0 + $1.durationHours } }

    var totalProgress: Double   { min(totalHours   / max(profile.totalRequiredHours,   1), 1.0) }
    var nightProgress: Double   { min(nightHours   / max(profile.nightRequiredHours,   1), 1.0) }
    var highwayProgress: Double { min(highwayHours / max(profile.highwayRequiredHours, 1), 1.0) }

    var remainingHours: Double      { max(profile.totalRequiredHours   - totalHours,  0) }
    var remainingNightHours: Double { max(profile.nightRequiredHours   - nightHours,  0) }

    var sessionCount: Int { sessions.count }
    var recentSessions: [DrivingSession] { Array(sessions.prefix(5)) }

    var isComplete: Bool {
        totalHours >= profile.totalRequiredHours &&
        (profile.nightRequiredHours == 0 || nightHours >= profile.nightRequiredHours)
    }

    // MARK: - Session CRUD

    func addSession(_ session: DrivingSession) {
        sessions.insert(session, at: 0)
        sessions.sort { $0.date > $1.date }
        saveSessions()
    }

    func updateSession(_ session: DrivingSession) {
        guard let idx = sessions.firstIndex(where: { $0.id == session.id }) else { return }
        sessions[idx] = session
        sessions.sort { $0.date > $1.date }
        saveSessions()
    }

    func deleteSession(_ session: DrivingSession) {
        sessions.removeAll { $0.id == session.id }
        saveSessions()
    }

    func deleteSessions(at offsets: IndexSet) {
        sessions.remove(atOffsets: offsets)
        saveSessions()
    }

    // MARK: - Private: jurisdiction helpers

    private func applyJurisdiction() {
        switch selectedCountry {
        case .custom:
            profile = savedCustomProfile
        default:
            let regions = selectedCountry.regions
            let match   = regions.first(where: { $0.id == selectedRegionId }) ?? regions.first
            if let match {
                selectedRegionId = match.id
                profile = match
            }
        }
        saveProfile()
    }

    // MARK: - Private: persistence

    private struct JurisdictionSelection: Codable {
        var country: JurisdictionCountry
        var regionId: UUID
    }

    private func loadJurisdiction() {
        if let data = try? Data(contentsOf: jurisdictionURL),
           let sel  = try? JSONDecoder().decode(JurisdictionSelection.self, from: data) {
            selectedCountry  = sel.country
            selectedRegionId = sel.regionId
        }
        applyJurisdiction()
    }

    private func saveJurisdiction() {
        let sel = JurisdictionSelection(country: selectedCountry, regionId: selectedRegionId)
        if let data = try? JSONEncoder().encode(sel) {
            try? data.write(to: jurisdictionURL, options: .atomic)
        }
    }

    private func loadCustomProfile() {
        guard let data    = try? Data(contentsOf: customProfileURL),
              let decoded = try? JSONDecoder().decode(RequirementsProfile.self, from: data) else { return }
        savedCustomProfile = decoded
    }

    private func saveCustomProfile() {
        if let data = try? JSONEncoder().encode(savedCustomProfile) {
            try? data.write(to: customProfileURL, options: .atomic)
        }
    }

    private func saveSessions() {
        if let data = try? JSONEncoder().encode(sessions) {
            try? data.write(to: sessionsURL, options: .atomic)
        }
    }

    private func loadSessions() {
        guard let data    = try? Data(contentsOf: sessionsURL),
              let decoded = try? JSONDecoder().decode([DrivingSession].self, from: data) else { return }
        sessions = decoded.sorted { $0.date > $1.date }
    }

    private func saveProfile() {
        if let data = try? JSONEncoder().encode(profile) {
            try? data.write(to: profileURL, options: .atomic)
        }
    }
}

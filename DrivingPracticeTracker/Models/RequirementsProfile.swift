import Foundation

// MARK: - Jurisdiction Country

enum JurisdictionCountry: String, Codable, CaseIterable, Identifiable {
    case australia     = "Australia"
    case unitedStates  = "United States"
    case unitedKingdom = "United Kingdom"
    case custom        = "Custom"

    var id: String { rawValue }

    var flag: String {
        switch self {
        case .australia:     return "🇦🇺"
        case .unitedStates:  return "🇺🇸"
        case .unitedKingdom: return "🇬🇧"
        case .custom:        return "⚙️"
        }
    }

    var regions: [RequirementsProfile] {
        switch self {
        case .australia:     return RequirementsProfile.australiaRegions
        case .unitedStates:  return RequirementsProfile.usRegions
        case .unitedKingdom: return RequirementsProfile.ukRegions
        case .custom:        return []
        }
    }

    /// Returns the first region, or nil for Custom
    var defaultRegion: RequirementsProfile? { regions.first }
}

// MARK: - Requirements Profile

struct RequirementsProfile: Identifiable, Codable, Equatable {
    var id: UUID
    var name: String
    var totalRequiredHours: Double
    var nightRequiredHours: Double
    var highwayRequiredHours: Double

    init(
        id: UUID = UUID(),
        name: String,
        totalRequiredHours: Double,
        nightRequiredHours: Double = 0,
        highwayRequiredHours: Double = 0
    ) {
        self.id = id
        self.name = name
        self.totalRequiredHours = totalRequiredHours
        self.nightRequiredHours = nightRequiredHours
        self.highwayRequiredHours = highwayRequiredHours
    }

    /// Returns a copy with specified fields replaced.
    func with(
        name: String? = nil,
        totalHours: Double? = nil,
        nightHours: Double? = nil,
        highwayHours: Double? = nil
    ) -> RequirementsProfile {
        RequirementsProfile(
            id: id,
            name: name ?? self.name,
            totalRequiredHours: totalHours ?? totalRequiredHours,
            nightRequiredHours: nightHours ?? nightRequiredHours,
            highwayRequiredHours: highwayHours ?? highwayRequiredHours
        )
    }

    // MARK: - Regional data (stable UUIDs)

    static let australiaRegions: [RequirementsProfile] = [
        RequirementsProfile(id: UUID(uuidString: "20000001-0000-0000-0000-000000000001")!, name: "NSW",
                            totalRequiredHours: 120, nightRequiredHours: 20),
        RequirementsProfile(id: UUID(uuidString: "20000001-0000-0000-0000-000000000002")!, name: "VIC",
                            totalRequiredHours: 120, nightRequiredHours: 10),
        RequirementsProfile(id: UUID(uuidString: "20000001-0000-0000-0000-000000000003")!, name: "QLD",
                            totalRequiredHours: 100, nightRequiredHours: 10),
        RequirementsProfile(id: UUID(uuidString: "20000001-0000-0000-0000-000000000004")!, name: "WA",
                            totalRequiredHours: 50,  nightRequiredHours: 5),
        RequirementsProfile(id: UUID(uuidString: "20000001-0000-0000-0000-000000000005")!, name: "SA",
                            totalRequiredHours: 75,  nightRequiredHours: 15),
        RequirementsProfile(id: UUID(uuidString: "20000001-0000-0000-0000-000000000006")!, name: "TAS",
                            totalRequiredHours: 60,  nightRequiredHours: 10),
    ]

    static let usRegions: [RequirementsProfile] = [
        RequirementsProfile(id: UUID(uuidString: "30000001-0000-0000-0000-000000000001")!, name: "California",
                            totalRequiredHours: 50, nightRequiredHours: 10),
        RequirementsProfile(id: UUID(uuidString: "30000001-0000-0000-0000-000000000002")!, name: "New York",
                            totalRequiredHours: 50, nightRequiredHours: 15),
        RequirementsProfile(id: UUID(uuidString: "30000001-0000-0000-0000-000000000003")!, name: "Texas",
                            totalRequiredHours: 30, nightRequiredHours: 10),
        RequirementsProfile(id: UUID(uuidString: "30000001-0000-0000-0000-000000000004")!, name: "Florida",
                            totalRequiredHours: 50, nightRequiredHours: 10),
    ]

    static let ukRegions: [RequirementsProfile] = [
        RequirementsProfile(id: UUID(uuidString: "40000001-0000-0000-0000-000000000001")!, name: "United Kingdom",
                            totalRequiredHours: 45, nightRequiredHours: 0),
    ]

    static var defaultCustomProfile: RequirementsProfile {
        RequirementsProfile(
            id: UUID(uuidString: "50000001-0000-0000-0000-000000000001")!,
            name: "My Custom Profile",
            totalRequiredHours: 100,
            nightRequiredHours: 10
        )
    }

    static var defaultProfile: RequirementsProfile { australiaRegions[0] }
}

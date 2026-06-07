import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var store: SessionStore
    @EnvironmentObject var detectionManager: DrivingDetectionManager
    @State private var detectionPermissionError: String?

    var body: some View {
        NavigationStack {
            Form {

                // ── Jurisdiction ─────────────────────────────────────────
                Section {
                    // Country drop-down
                    Picker("Country", selection: Binding(
                        get: { store.selectedCountry },
                        set: { store.selectCountry($0) }
                    )) {
                        ForEach(JurisdictionCountry.allCases) { country in
                            Text("\(country.flag)  \(country.rawValue)").tag(country)
                        }
                    }
                    .pickerStyle(.menu)

                    // State / Region drop-down — hidden for UK (single rule) and Custom
                    if store.selectedCountry != .custom,
                       store.selectedCountry.regions.count > 1 {
                        Picker("State / Region", selection: Binding(
                            get: { store.selectedRegionId },
                            set: { id in
                                if let r = store.selectedCountry.regions.first(where: { $0.id == id }) {
                                    store.selectRegion(r)
                                }
                            }
                        )) {
                            ForEach(store.selectedCountry.regions) { region in
                                Text(region.name).tag(region.id)
                            }
                        }
                        .pickerStyle(.menu)
                    }

                    // Custom inline editor — replaces the old modal sheet
                    if store.selectedCountry == .custom {
                        CustomProfileInlineView()
                    }

                } header: {
                    Text("Jurisdiction")
                } footer: {
                    if store.selectedCountry == .custom {
                        Text("Your custom values are saved automatically. Switching to another country and back restores them.")
                    }
                }

                // ── Requirements summary (read-only) ──────────────────────
                Section("Requirements") {
                    LabeledContent("Total Hours",
                                   value: String(format: "%.0f h", store.profile.totalRequiredHours))
                    if store.profile.nightRequiredHours > 0 {
                        LabeledContent("Night Hours",
                                       value: String(format: "%.0f h", store.profile.nightRequiredHours))
                    }
                    if store.profile.highwayRequiredHours > 0 {
                        LabeledContent("Highway Hours",
                                       value: String(format: "%.0f h", store.profile.highwayRequiredHours))
                    }
                }

                // ── Automatic detection ───────────────────────────────────
                Section {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("Auto-detect Driving")
                            Text("Motion sensor detects drives and prompts you to log them.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Toggle("", isOn: Binding(
                            get: { detectionManager.isEnabled },
                            set: { enabled in
                                detectionPermissionError = nil
                                if enabled {
                                    Task {
                                        let ok = await detectionManager.requestPermissionsAndEnable()
                                        if !ok {
                                            detectionPermissionError =
                                                "Allow Motion & Fitness and Notifications in Settings → Privacy."
                                        }
                                    }
                                } else {
                                    detectionManager.disable()
                                }
                            }
                        ))
                        .labelsHidden()
                    }

                    if detectionManager.isDriving {
                        Label("Drive in progress…", systemImage: "car.fill")
                            .foregroundStyle(.green)
                            .font(.subheadline)
                    }

                    if let err = detectionPermissionError {
                        Text(err)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }

                } header: {
                    Text("Automatic Detection")
                } footer: {
                    Text("Sessions shorter than 5 minutes are ignored. A 3-minute stop is needed before a session is confirmed.")
                }

                // ── Siri shortcuts hint ───────────────────────────────────
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Siri Shortcuts", systemImage: "waveform")
                            .font(.headline)
                        Text("Ask Siri:")
                        Group {
                            Text("\"Log driving in Driving Tracker\"")
                            Text("\"Check driving progress in Driving Tracker\"")
                        }
                        .italic()
                        .foregroundStyle(.secondary)
                        Text("Also available in the Shortcuts app.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                }

                // ── Data ─────────────────────────────────────────────────
                Section("Data") {
                    NavigationLink("Export Sessions (CSV)") {
                        ExportView()
                    }
                }
            }
            .navigationTitle("Settings")
        }
    }
}

// MARK: - Custom Profile Inline Editor

struct CustomProfileInlineView: View {
    @EnvironmentObject var store: SessionStore

    var body: some View {
        Group {
            // Name field
            HStack {
                Text("Profile Name")
                Spacer()
                TextField("Name", text: Binding(
                    get: { store.savedCustomProfile.name },
                    set: { store.updateCustomProfile(store.savedCustomProfile.with(name: $0)) }
                ))
                .multilineTextAlignment(.trailing)
                .foregroundStyle(.secondary)
            }

            // Total hours stepper
            Stepper(
                value: Binding(
                    get: { store.savedCustomProfile.totalRequiredHours },
                    set: { store.updateCustomProfile(store.savedCustomProfile.with(totalHours: $0)) }
                ),
                in: 5...500, step: 5
            ) {
                HStack {
                    Text("Total Hours")
                    Spacer()
                    Text(String(format: "%.0f h", store.savedCustomProfile.totalRequiredHours))
                        .foregroundStyle(.secondary)
                }
            }

            // Night hours stepper
            Stepper(
                value: Binding(
                    get: { store.savedCustomProfile.nightRequiredHours },
                    set: { store.updateCustomProfile(store.savedCustomProfile.with(nightHours: $0)) }
                ),
                in: 0...200, step: 1
            ) {
                HStack {
                    Text("Night Hours")
                    Spacer()
                    Text(String(format: "%.0f h", store.savedCustomProfile.nightRequiredHours))
                        .foregroundStyle(.secondary)
                }
            }

            // Highway hours stepper
            Stepper(
                value: Binding(
                    get: { store.savedCustomProfile.highwayRequiredHours },
                    set: { store.updateCustomProfile(store.savedCustomProfile.with(highwayHours: $0)) }
                ),
                in: 0...200, step: 1
            ) {
                HStack {
                    Text("Highway Hours")
                    Spacer()
                    Text(String(format: "%.0f h", store.savedCustomProfile.highwayRequiredHours))
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

// MARK: - Export View (unchanged)

struct ExportView: View {
    @EnvironmentObject var store: SessionStore
    @State private var csvText = ""

    var body: some View {
        ScrollView {
            Text(csvText)
                .font(.system(.caption, design: .monospaced))
                .padding()
                .textSelection(.enabled)
        }
        .navigationTitle("Export CSV")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                ShareLink(item: csvText, subject: Text("Driving Sessions"))
            }
        }
        .onAppear { csvText = buildCSV() }
    }

    private func buildCSV() -> String {
        var lines = ["Date,Duration (min),Hours,Conditions,Supervisor,Notes"]
        for s in store.sessions.sorted(by: { $0.date < $1.date }) {
            let conditions = s.conditions.map(\.rawValue).joined(separator: "|")
            let notes      = s.notes.replacingOccurrences(of: ",", with: ";")
            lines.append(
                "\(s.date.ISO8601Format()),\(s.durationMinutes),\(String(format:"%.2f",s.durationHours)),\(conditions),\(s.supervisor),\(notes)"
            )
        }
        return lines.joined(separator: "\n")
    }
}

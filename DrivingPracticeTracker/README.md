# Driving Practice Tracker

An iOS app to log driving practice sessions and track progress toward meeting learner driver test requirements — with in-app voice logging and full Siri / Shortcuts integration.

---

## Features

| Feature | Description |
|---|---|
| **Session logging** | Log date, duration, road conditions, supervisor, and notes |
| **Progress dashboard** | Circular progress rings for total, night, and highway hours |
| **Voice logging** | Speak a session naturally; the app extracts duration, conditions, and supervisor |
| **Siri integration** | Log a drive or check your progress without opening the app |
| **Shortcuts app** | Customisable Siri shortcuts for common actions |
| **CSV export** | Share all sessions as a CSV via the Share Sheet |
| **Jurisdiction presets** | NSW / VIC / QLD / WA / California / New York / UK, or fully custom |

---

## Supported Siri Phrases

After installing the app, these phrases are automatically registered with Siri (no setup required):

**Log a session:**
- *"Log driving in Driving Tracker"*
- *"Record a driving session in Driving Tracker"*
- *"Add driving time to Driving Tracker"*

**Check progress:**
- *"Check my driving progress in Driving Tracker"*
- *"How many driving hours in Driving Tracker"*
- *"How close am I to my driving test in Driving Tracker"*

You can also find and customise these in the **Shortcuts** app under *Driving Tracker*.

---

## Voice Logging (in-app)

Tap the **mic icon** on the Log Drive tab (or the mic button in the toolbar) and say something like:

- *"Drove 45 minutes on the highway"*
- *"One hour night driving with Sarah"*
- *"30 minutes urban driving in the rain with Mum"*
- *"An hour and a half rural driving with Dad"*

The parser detects:
- **Duration** — numeric ("45 minutes", "2 hours") or written ("an hour", "half an hour")
- **Night** — "night", "dark", "evening"
- **Highway** — "highway", "motorway", "freeway", "expressway"
- **Rain** — "rain", "raining", "wet", "drizzle"
- **Urban** — "urban", "city", "town", "suburb"
- **Rural** — "rural", "country", "countryside"
- **Supervisor** — "with [Name]", "with my mum Sarah", "with instructor Dave"

Review the parsed result, then tap **Use This Session** to pre-fill the log form.

---

## Xcode Setup

### Requirements
- Xcode 15+
- iOS 16+ deployment target
- Swift 5.9+

### Steps

1. **Create a new Xcode project**
   - Template: *App* (SwiftUI, Swift)
   - Bundle ID: `com.yourname.DrivingPracticeTracker`
   - Minimum Deployment: iOS 16.0

2. **Add all source files**
   Add all `.swift` files from this folder into the project, keeping the folder structure as groups:
   ```
   App/
   Models/
   ViewModels/
   Views/
   Voice/
   Intents/
   ```

3. **Replace Info.plist**
   Merge the keys from `Info.plist` in this repo into your project's `Info.plist`, or replace it entirely.

4. **Add frameworks**
   In *Build Phases → Link Binary with Libraries*, confirm these are present (Xcode usually adds them automatically):
   - `Speech.framework`
   - `AVFoundation.framework`
   - `AppIntents.framework`

5. **Enable Siri capability**
   - Go to your target → *Signing & Capabilities*
   - Click **+ Capability** → add **Siri**

6. **Run** on a real device (voice recognition requires hardware; simulator has limited support)

---

## Architecture

```
DrivingPracticeTracker/
├── App/
│   ├── DrivingPracticeTrackerApp.swift   @main entry point
│   └── ContentView.swift                 TabView container
├── Models/
│   ├── DrivingSession.swift              Codable session model + DrivingCondition enum
│   └── RequirementsProfile.swift        Jurisdiction requirements + presets
├── ViewModels/
│   └── SessionStore.swift               ObservableObject singleton, JSON persistence
├── Views/
│   ├── DashboardView.swift              Progress rings, stat cards, recent sessions
│   ├── LogSessionView.swift             Manual session form
│   ├── VoiceLogView.swift               Voice capture + parsing UI
│   ├── SessionListView.swift            Searchable history list
│   ├── SessionDetailView.swift          Session detail + delete
│   └── SettingsView.swift               Jurisdiction picker, custom requirements, CSV export
├── Voice/
│   └── VoiceLogManager.swift            SFSpeechRecognizer + NLP parser
└── Intents/
    ├── LogDrivingSessionIntent.swift     Siri: log a session
    ├── GetProgressIntent.swift           Siri: check progress
    └── AppShortcuts.swift               AppShortcutsProvider — auto-registers with Siri
```

---

## Privacy

- Microphone audio is processed entirely on-device via `SFSpeechRecognizer`.
- No session data is sent to any server; all data is stored locally in the app's Documents directory as JSON.
- The app does not use analytics or crash-reporting SDKs.

---

## Licence

MIT

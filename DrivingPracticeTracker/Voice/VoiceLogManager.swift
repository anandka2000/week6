import Foundation
import Speech
import AVFoundation

/// Manages microphone capture and on-device speech-to-text transcription,
/// then parses natural language into a DrivingSession.
@MainActor
class VoiceLogManager: NSObject, ObservableObject, SFSpeechRecognizerDelegate {

    // MARK: - Published state

    @Published var transcript: String = ""
    @Published var isRecording: Bool = false
    @Published var errorMessage: String?
    @Published var parsedSession: ParsedSession?

    // MARK: - Parsed output type

    struct ParsedSession {
        var durationMinutes: Int
        var conditions: [DrivingCondition]
        var supervisor: String
    }

    // MARK: - Private properties

    private let speechRecognizer: SFSpeechRecognizer? = {
        // Prefer the device locale; fall back to en-AU then en-US
        let locales: [Locale] = [.current, Locale(identifier: "en-AU"), Locale(identifier: "en-US")]
        return locales.compactMap { SFSpeechRecognizer(locale: $0) }
                      .first(where: { $0.isAvailable })
            ?? locales.compactMap { SFSpeechRecognizer(locale: $0) }.first
    }()

    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let audioEngine = AVAudioEngine()

    override init() {
        super.init()
        speechRecognizer?.delegate = self
    }

    // MARK: - SFSpeechRecognizerDelegate
    // nonisolated because SFSpeechRecognizer calls this from an arbitrary thread.

    nonisolated func speechRecognizer(_ speechRecognizer: SFSpeechRecognizer,
                                      availabilityDidChange available: Bool) {
        Task { @MainActor [weak self] in
            guard let self else { return }
            if !available {
                self.errorMessage = "Speech recognition became unavailable."
                if self.isRecording { self.stopRecording() }
            }
        }
    }

    // MARK: - Start / Stop

    func startRecording() async {
        // Cancel any previous session before starting a new one
        if isRecording { stopRecording() }

        // --- Microphone permission ---
        // Use AVAudioSession consistently (iOS 16+); avoids the iOS-17-only AVAudioApplication API.
        let micGranted = await withCheckedContinuation { (cont: CheckedContinuation<Bool, Never>) in
            switch AVAudioSession.sharedInstance().recordPermission {
            case .granted:
                cont.resume(returning: true)
            case .denied:
                cont.resume(returning: false)
            case .undetermined:
                AVAudioSession.sharedInstance().requestRecordPermission { cont.resume(returning: $0) }
            @unknown default:
                cont.resume(returning: false)
            }
        }

        guard micGranted else {
            errorMessage = "Microphone access denied. Enable it in Settings → Privacy & Security → Microphone."
            return
        }

        // --- Speech Recognition permission ---
        let speechGranted = await withCheckedContinuation { (cont: CheckedContinuation<Bool, Never>) in
            switch SFSpeechRecognizer.authorizationStatus() {
            case .authorized:
                cont.resume(returning: true)
            case .denied, .restricted:
                cont.resume(returning: false)
            case .notDetermined:
                SFSpeechRecognizer.requestAuthorization { cont.resume(returning: $0 == .authorized) }
            @unknown default:
                cont.resume(returning: false)
            }
        }

        guard speechGranted else {
            errorMessage = "Speech Recognition denied. Enable it in Settings → Privacy & Security → Speech Recognition."
            return
        }

        guard let recognizer = speechRecognizer, recognizer.isAvailable else {
            errorMessage = "Speech recognition is not available on this device or for the current region."
            return
        }

        errorMessage  = nil
        transcript    = ""
        parsedSession = nil

        do {
            try setupAudioEngine()
            isRecording = true
        } catch {
            cleanupAudio()
            errorMessage = "Could not start recording: \(error.localizedDescription)"
        }
    }

    func stopRecording() {
        // Guard prevents double-cleanup when the recognition callback also calls stopRecording.
        guard isRecording else { return }
        isRecording = false
        cleanupAudio()
        if !transcript.isEmpty {
            parsedSession = parseTranscript(transcript)
        }
    }

    // MARK: - Audio engine setup

    private func setupAudioEngine() throws {
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.taskHint = .dictation
        recognitionRequest = request

        // Configure AVAudioSession for recording
        let audioSession = AVAudioSession.sharedInstance()
        try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
        try audioSession.setActive(true, options: .notifyOthersOnDeactivation)

        // Start speech recognition task.
        // The closure is called on a background thread by SFSpeechRecognizer.
        // We do NOT capture self in the outer closure to avoid @MainActor isolation issues.
        // All self access is inside the inner Task which is explicitly @MainActor.
        recognitionTask = speechRecognizer?.recognitionTask(with: request) { result, error in
            Task { @MainActor [weak self] in
                guard let self else { return }

                if let result {
                    self.transcript = result.bestTranscription.formattedString
                }

                if let error {
                    let nsError = error as NSError
                    // Ignore expected cancellation codes:
                    //   1110 – kLSRErrorDomain/cancelled
                    //    216 – kAFAssistantErrorDomain/request cancelled
                    //    203 – kAFAssistantErrorDomain/request not yet ready
                    let isCancellation = (nsError.code == 1110 || nsError.code == 216 || nsError.code == 203)
                    if !isCancellation {
                        self.errorMessage = error.localizedDescription
                    }
                    self.stopRecording()
                } else if result?.isFinal == true {
                    self.stopRecording()
                }
            }
        }

        // FIX: Remove any existing tap before installing.
        // Without this, calling startRecording() a second time (e.g. after an error)
        // throws "required condition is false: !_tapList.hasTap(forBusNumber: bus)"
        let inputNode = audioEngine.inputNode
        inputNode.removeTap(onBus: 0)

        let format = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 4096, format: format) { buffer, _ in
            request.append(buffer)
        }

        audioEngine.prepare()
        try audioEngine.start()
    }

    // MARK: - Cleanup

    private func cleanupAudio() {
        // Correct order: signal end of audio → cancel task → stop engine → remove tap → deactivate session
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionTask    = nil
        recognitionRequest = nil

        if audioEngine.isRunning {
            audioEngine.stop()
        }
        audioEngine.inputNode.removeTap(onBus: 0)

        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    // MARK: - Natural Language Parsing

    func parseTranscript(_ text: String) -> ParsedSession {
        let lower = text.lowercased()
        return ParsedSession(
            durationMinutes: max(parseDuration(from: lower), 5),
            conditions:      parseConditions(from: lower),
            supervisor:      parseSupervisor(from: text)  // preserve original casing for names
        )
    }

    private func parseDuration(from text: String) -> Int {
        var hours = 0, minutes = 0
        if let h = firstInt(#"(\d+)\s*(?:hours?|hrs?)"#,    in: text) { hours   = h }
        if let m = firstInt(#"(\d+)\s*(?:minutes?|mins?)"#, in: text) { minutes = m }

        if hours == 0 && minutes == 0 {
            if      text.contains("two hours")               { hours   = 2  }
            else if text.contains("one hour")
                 || text.contains("an hour")                 { hours   = 1  }
            else if text.contains("half an hour")
                 || text.contains("half hour")               { minutes = 30 }
            else if text.contains("quarter")                 { minutes = 15 }
        }
        return hours * 60 + minutes
    }

    private func firstInt(_ pattern: String, in text: String) -> Int? {
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
              let range = Range(match.range(at: 1), in: text) else { return nil }
        return Int(text[range])
    }

    private func parseConditions(from lower: String) -> [DrivingCondition] {
        var result: [DrivingCondition] = []
        let isNight = lower.contains("night") || lower.contains("dark") || lower.contains("evening")
        result.append(isNight ? .night : .day)

        let map: [(DrivingCondition, [String])] = [
            (.highway, ["highway", "motorway", "freeway", "expressway", "dual carriageway"]),
            (.rain,    ["rain", "raining", "wet", "drizzl", "shower"]),
            (.urban,   ["urban", "city", "town", "suburb", "street"]),
            (.rural,   ["rural", "country", "countryside", "backroad"]),
        ]
        for (condition, keywords) in map where keywords.contains(where: { lower.contains($0) }) {
            result.append(condition)
        }
        return result
    }

    private func parseSupervisor(from text: String) -> String {
        let pattern = #"(?i)\bwith\s+(?:my\s+)?(?:mum|mom|dad|father|mother|instructor|supervisor|teacher|friend\s+)?([A-Z][a-z]+)"#
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
              let range = Range(match.range(at: 1), in: text) else { return "" }
        return String(text[range])
    }
}

import BackgroundTasks
import Foundation
import Observation
import UserNotifications

/// Loads `app.json`, keeps the last copy for offline, and notifies on news worth acting on.
@MainActor
@Observable
final class FeedStore {
    nonisolated static let refreshTask = "com.chamberneezy.nbafantasy.refresh"

    private(set) var feed: Feed?
    private(set) var error: String?
    private(set) var loading = false

    private let cacheURL = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("app.json")
    /// Alerts already sent. Renamed from "seenNews" in build 2 of the alerts: the old list had swallowed
    /// alerts that never showed (posted while the app was open), so everything current alerts once more.
    private let seenKey = "seenAlerts"
    private(set) var notificationsAllowed = true

    init() {
        if let data = try? Data(contentsOf: cacheURL) {
            feed = try? Feed.decode(data)
        }
    }

    func refresh() async {
        loading = true
        defer { loading = false }
        do {
            let fresh = try await Self.download()
            try? fresh.data.write(to: cacheURL)
            feed = fresh.feed
            error = nil
            await notifyNew(fresh.feed)
        } catch {
            self.error = "Could not load: \(error.localizedDescription)"
        }
    }

    nonisolated static func download() async throws -> (feed: Feed, data: Data) {
        var request = URLRequest(url: Feed.url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        let (data, _) = try await URLSession.shared.data(for: request)
        return (try Feed.decode(data), data)
    }

    // MARK: notifications

    func askForNotifications() async {
        let center = UNUserNotificationCenter.current()
        center.delegate = Banner.shared
        _ = try? await center.requestAuthorization(options: [.alert, .sound, .badge])
        notificationsAllowed = await center.notificationSettings().authorizationStatus == .authorized
    }

    /// The nightly recap once a night's games are in; injuries when they happen (a new or changed status for
    /// one of mine, one of my opponent's ruled out); minutes opening up for someone I own or can add.
    private func notifyNew(_ feed: Feed) async {
        var seen = Set(UserDefaults.standard.stringArray(forKey: seenKey) ?? [])
        var alerts: [(String, String, String)] = []
        // Fresh news only: an injury reported more than two days ago is not news, even to a fresh install.
        let fresh = Dates.iso(Date(timeIntervalSinceNow: -2 * 86_400))
        var injuries: [(id: String, title: String, body: String, reported: String)] = []
        for injury in feed.injuries?.mine ?? feed.news.mineOut {
            let id = "inj:\(injury.playerName):\(injury.status):\(injury.reported)"
            guard !seen.contains(id) else { continue }
            let back = injury.returnDate.isEmpty ? "" : " · back ~\(Dates.short(injury.returnDate))"
            injuries.append((id, "\(injury.playerName): \(injury.status)\(back)", injury.note, injury.reported))
        }
        for injury in (feed.injuries?.theirs ?? feed.news.opponentOut) where injury.status == "Out" {
            let id = "opp:\(injury.playerName):\(injury.reported)"
            guard !seen.contains(id) else { continue }
            injuries.append((id, "\(feed.opponent ?? "Opponent")'s \(injury.playerName): out", injury.note, injury.reported))
        }
        for alert in injuries { seen.insert(alert.id) }
        alerts += injuries.filter { $0.reported >= fresh }.map { ($0.id, $0.title, $0.body) }
        // Only news worth acting on: your player gets more, or a pickup beats your weakest.
        for chance in feed.news.opportunities where !seen.contains("op:" + chance.id) {
            let worth = chance.gains.filter { $0.owner == "mine" || $0.beatsWeakest == true }
            guard !worth.isEmpty else { continue }
            seen.insert("op:" + chance.id)
            let names = worth.prefix(2).map { gain -> String in
                let points = gain.now.flatMap { now in gain.bumped.map { " \(LineText.fmt(now.pts))→\(LineText.fmt($0.pts)) pts" } } ?? ""
                return "\(gain.playerName) (\(gain.ownerLabel.lowercased()))\(points), \(gain.certainty.level) certainty"
            }.joined(separator: "; ")
            alerts.append(("op:" + chance.id, "\(chance.playerName) out, \(chance.daysOut) days", names))
        }
        // The morning update: last night's lines, the night and the week score, where the week is heading.
        if let recap = feed.recap, recap.played, recap.date >= fresh, !seen.contains("recap:" + recap.date) {
            seen.insert("recap:" + recap.date)
            let lines = recap.mine.prefix(4).map { "\($0.playerName.split(separator: " ").last.map(String.init) ?? $0.playerName) \($0.short)" }.joined(separator: "; ")
            var tally = [recap.night.map { "Night \($0.text)" }, recap.weekScore.map { "week \($0.text)\(recap.opponent.map { " vs \($0)" } ?? "")" }].compactMap { $0 }.joined(separator: ", ")
            if let outlook = feed.score?.outlook, recap.week == feed.week {
                tally += ". By Sunday: \(outlook.yours) lean yours, \(outlook.coinFlip) coin flip\(outlook.coinFlip == 1 ? "" : "s"), \(outlook.his) lean his"
            }
            alerts.append(("recap:" + recap.date, "Last night · \(Dates.short(recap.date))", [lines, tally].filter { !$0.isEmpty }.joined(separator: ". ")))
        }
        UserDefaults.standard.set(Array(seen), forKey: seenKey)
        for (id, title, body) in alerts {
            let content = UNMutableNotificationContent()
            content.title = title
            content.body = body
            content.sound = .default
            try? await UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: content, trigger: nil))
        }
    }

    // MARK: background refresh (iOS decides when; usually a few times a day)

    nonisolated static func scheduleBackgroundRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: refreshTask)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 60 * 60)
        try? BGTaskScheduler.shared.submit(request)
    }
}

/// iOS hides a notification posted while the app is open unless asked; most refreshes happen exactly then.
final class Banner: NSObject, UNUserNotificationCenterDelegate {
    static let shared = Banner()

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }
}

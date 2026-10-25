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
    private let seenKey = "seenNews"

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
        _ = try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])
    }

    /// One alert per news item: my player out, or minutes opening up for someone I own or can add.
    private func notifyNew(_ feed: Feed) async {
        var seen = Set(UserDefaults.standard.stringArray(forKey: seenKey) ?? [])
        var alerts: [(String, String, String)] = []
        for injury in feed.news.mineOut where !seen.contains("out:" + injury.id) {
            seen.insert("out:" + injury.id)
            alerts.append(("out:" + injury.id, "\(injury.playerName): \(injury.status)", injury.note))
        }
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
        // The morning update: once a new night is in the score, one line with where the week stands.
        if let score = feed.score, let through = score.through, let text = score.text,
           !seen.contains("score:" + through) {
            seen.insert("score:" + through)
            let outlook = score.outlook
            alerts.append((
                "score:" + through,
                "Week \(feed.week): \(text) vs \(feed.opponent ?? "opponent")",
                "Through \(Dates.short(through)). By Sunday: \(outlook.yours) lean yours, \(outlook.coinFlip) coin flip\(outlook.coinFlip == 1 ? "" : "s"), \(outlook.his) lean his."
            ))
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

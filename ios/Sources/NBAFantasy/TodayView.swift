import SwiftUI

struct TodayView: View {
    @Environment(FeedStore.self) private var store

    var body: some View {
        NavigationStack {
            List {
                if let feed = store.feed {
                    BrandSection("Week \(feed.week) score") {
                        ScoreCard(feed: feed)
                    }
                    if let recap = feed.recap, recap.played {
                        BrandSection("Last night · \(Dates.short(recap.date))", footer: recapFooter(recap)) {
                            RecapRows(title: "Yours", lines: recap.mine, color: Theme.blue)
                            if !recap.theirs.isEmpty { RecapRows(title: recap.opponent ?? "Opponent", lines: recap.theirs, color: Theme.red) }
                        }
                    }
                    BrandSection("Starts per day vs \(feed.opponent ?? "—")", footer: feed.addsLeft.map { "\($0) add\($0 == 1 ? "" : "s") left this week" }) {
                        WeekStrip(days: feed.days, today: feed.today.date)
                    }
                    BrandSection("Start today") {
                        if feed.today.starters.isEmpty { Text("Nobody plays today").font(Theme.ui(15)).foregroundStyle(Theme.mute) }
                        ForEach(feed.today.starters) { GameRow(game: $0) }
                    }
                    if !feed.today.bench.isEmpty {
                        BrandSection("Plays, but sits") {
                            ForEach(feed.today.bench) { GameRow(game: $0) }
                        }
                    }
                    if !feed.today.off.isEmpty {
                        BrandSection("No game") {
                            Text(feed.today.off.joined(separator: " · ")).font(Theme.ui(13)).foregroundStyle(Theme.mute)
                        }
                    }
                    BrandSection {
                        if !store.notificationsAllowed {
                            Text("Notifications are off: Settings → NBA Fantasy → Notifications").font(Theme.ui(12.5, .semibold)).foregroundStyle(Theme.red)
                        }
                        Stamp(feed: feed, error: store.error)
                    }
                } else if let error = store.error {
                    Text(error).font(Theme.ui(14)).foregroundStyle(Theme.red)
                } else {
                    ProgressView()
                }
            }
            .brandScreen("Today")
            .refreshable { await store.refresh() }
        }
    }
}

private func recapFooter(_ recap: Recap) -> String? {
    let parts = [recap.night.map { "Night \($0.text)" }, recap.weekScore.map { "week \($0.text) after it" }].compactMap { $0 }
    return parts.isEmpty ? nil : parts.joined(separator: " · ")
}

/// One team's starters last night, one line each.
struct RecapRows: View {
    let title: String
    let lines: [RecapLine]
    let color: Color

    var body: some View {
        Text(title.uppercased()).font(Theme.display(12)).kerning(1).foregroundStyle(color)
        if lines.isEmpty { Text("No starter played").font(Theme.ui(13)).foregroundStyle(Theme.mute) }
        ForEach(lines) { line in
            HStack(alignment: .firstTextBaseline) {
                Text(line.playerName).font(Theme.ui(14, .semibold)).foregroundStyle(Theme.ink).lineLimit(1)
                Spacer()
                Text(line.short).font(Theme.ui(12).monospacedDigit()).foregroundStyle(Theme.ink).lineLimit(1).minimumScaleFactor(0.8)
            }
        }
    }
}

struct WeekStrip: View {
    let days: [Day]
    let today: String

    var body: some View {
        HStack(spacing: 0) {
            ForEach(days) { day in
                VStack(spacing: 3) {
                    Text(day.dow.uppercased()).font(Theme.ui(10.5, .semibold)).foregroundStyle(Theme.mute)
                    Text("\(day.myStarts)").font(Theme.display(22)).foregroundStyle(Theme.blue)
                    Text("\(day.theirPlayers)").font(Theme.display(14)).foregroundStyle(Theme.red.opacity(0.85))
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
                .background(day.date == today ? Theme.blue.opacity(0.12) : .clear, in: RoundedRectangle(cornerRadius: 10))
                .opacity(day.past ? 0.4 : 1)
            }
        }
        .accessibilityLabel("Starts per day: mine in blue, his in red")
    }
}

struct GameRow: View {
    let game: Game

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text(game.seat ?? "BN")
                .font(Theme.display(13))
                .foregroundStyle(game.seat == nil ? Theme.mute : .white)
                .frame(width: 34, height: 24)
                .background(game.seat == nil ? Theme.mute.opacity(0.15) : Theme.heading, in: RoundedRectangle(cornerRadius: 6))
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(game.playerName).font(Theme.ui(16, .semibold)).foregroundStyle(Theme.ink)
                    if !game.status.isEmpty { Pill(text: game.status, color: Theme.red) }
                }
                Text("\(game.team) \(game.home ? "vs" : "@") \(game.opp)\(tip)")
                    .font(Theme.ui(12.5)).foregroundStyle(Theme.mute)
                if let line = game.line {
                    Text(LineText.short(line)).font(Theme.ui(12).monospacedDigit()).foregroundStyle(Theme.ink)
                }
            }
        }
        .padding(.vertical, 2)
    }

    private var tip: String {
        guard let text = game.tipUtc, let date = ISO8601DateFormatter().date(from: text) else { return "" }
        return " · " + date.formatted(date: .omitted, time: .shortened)
    }
}

enum LineText {
    static func short(_ line: Line) -> String {
        var parts: [String] = []
        if let minutes = line.min { parts.append("\(Int(minutes.rounded())) min") }
        parts += [
            "\(fmt(line.pts)) pts", "\(fmt(line.reb)) reb", "\(fmt(line.ast)) ast",
            "\(fmt(line.fg3m)) 3s", "\(fmt(line.stl)) stl", "\(fmt(line.blk)) blk",
        ]
        return parts.joined(separator: " · ")
    }

    static func fmt(_ value: Double) -> String { String(format: "%.1f", value) }
}

struct Stamp: View {
    let feed: Feed
    let error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("Box scores through \(feed.logsThrough.map(Dates.short) ?? "—")")
            Text("Updated \(published)")
            if let error { Text(error).foregroundStyle(Theme.red) }
        }
        .font(Theme.ui(11.5))
        .foregroundStyle(Theme.mute)
    }

    private var published: String {
        guard let date = ISO8601DateFormatter().date(from: feed.publishedAt) else { return feed.publishedAt }
        return date.formatted(.relative(presentation: .named))
    }
}

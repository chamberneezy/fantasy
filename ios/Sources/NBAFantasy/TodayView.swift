import SwiftUI

struct TodayView: View {
    @Environment(FeedStore.self) private var store

    var body: some View {
        NavigationStack {
            List {
                if let feed = store.feed {
                    Section {
                        WeekStrip(days: feed.days, today: feed.today.date)
                    } header: {
                        Text("Week \(feed.week) vs \(feed.opponent ?? "—")")
                    } footer: {
                        if let adds = feed.addsLeft { Text("\(adds) add\(adds == 1 ? "" : "s") left this week") }
                    }
                    Section("Start today") {
                        if feed.today.starters.isEmpty { Text("Nobody plays today").foregroundStyle(.secondary) }
                        ForEach(feed.today.starters) { GameRow(game: $0) }
                    }
                    if !feed.today.bench.isEmpty {
                        Section("Plays, but sits") {
                            ForEach(feed.today.bench) { GameRow(game: $0) }
                        }
                    }
                    if !feed.today.off.isEmpty {
                        Section("No game") {
                            Text(feed.today.off.joined(separator: " · ")).font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    Section {
                        Stamp(feed: feed, error: store.error)
                    }
                } else if let error = store.error {
                    Text(error).foregroundStyle(.red)
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Today")
            .refreshable { await store.refresh() }
        }
    }
}

struct WeekStrip: View {
    let days: [Day]
    let today: String

    var body: some View {
        HStack(spacing: 0) {
            ForEach(days) { day in
                VStack(spacing: 4) {
                    Text(day.dow).font(.caption2).foregroundStyle(.secondary)
                    Text("\(day.myStarts)").font(.headline)
                    Text("\(day.theirPlayers)").font(.caption).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
                .background(day.date == today ? Color.accentColor.opacity(0.15) : .clear, in: RoundedRectangle(cornerRadius: 8))
                .opacity(day.past ? 0.45 : 1)
            }
        }
        .accessibilityLabel("Starts per day, mine over his")
    }
}

struct GameRow: View {
    let game: Game

    var body: some View {
        HStack(alignment: .top) {
            Text(game.seat ?? "BN")
                .font(.caption.bold())
                .frame(width: 30)
                .padding(.vertical, 3)
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 5))
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(game.playerName).font(.body.weight(.semibold))
                    if !game.status.isEmpty {
                        Text(game.status).font(.caption2.bold()).foregroundStyle(.red)
                    }
                }
                Text("\(game.team) \(game.home ? "vs" : "@") \(game.opp)\(tip)")
                    .font(.caption).foregroundStyle(.secondary)
                if let line = game.line {
                    Text(LineText.short(line)).font(.caption.monospacedDigit())
                }
            }
        }
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
            Text("Box scores through \(feed.logsThrough ?? "—")")
            Text("Published \(published)")
            if let error { Text(error).foregroundStyle(.red) }
        }
        .font(.caption2)
        .foregroundStyle(.secondary)
    }

    private var published: String {
        guard let date = ISO8601DateFormatter().date(from: feed.publishedAt) else { return feed.publishedAt }
        return date.formatted(.relative(presentation: .named))
    }
}

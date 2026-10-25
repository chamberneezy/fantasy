import SwiftUI

/// Who is out, who gets his minutes, and what that does to their lines. Yours and pickups first.
struct NewsView: View {
    @Environment(FeedStore.self) private var store

    var body: some View {
        NavigationStack {
            List {
                if let news = store.feed?.news {
                    if !news.mineOut.isEmpty {
                        Section("Your players out") {
                            ForEach(news.mineOut) { InjuryRow(injury: $0) }
                        }
                    }
                    if !news.opponentOut.isEmpty {
                        Section("Opponent's players out") {
                            ForEach(news.opponentOut) { InjuryRow(injury: $0) }
                        }
                    }
                    Section {
                        if news.opportunities.isEmpty { Text("No new absences").foregroundStyle(.secondary) }
                        ForEach(news.opportunities) { chance in
                            NavigationLink { OpportunityDetail(chance: chance, weakest: news.weakest, record: news.trackRecord) } label: { OpportunityRow(chance: chance) }
                        }
                    } header: {
                        Text("Minutes opening up")
                    } footer: {
                        Text("From games with and without him, this season counted 3× last season. \"Likely free\" means he is on no roster you pasted: check Yahoo.")
                    }
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("News")
            .refreshable { await store.refresh() }
        }
    }
}

struct InjuryRow: View {
    let injury: Injury

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(injury.playerName).font(.body.weight(.semibold))
                Text(injury.status).font(.caption.bold()).foregroundStyle(.red)
                Spacer()
                if !injury.returnDate.isEmpty { Text("back ~\(Dates.short(injury.returnDate))").font(.caption).foregroundStyle(.secondary) }
            }
            if !injury.note.isEmpty { Text(injury.note).font(.caption).foregroundStyle(.secondary) }
        }
    }
}

struct CertaintyBadge: View {
    let level: String

    var body: some View {
        Text(level)
            .font(.caption2.bold())
            .padding(.horizontal, 6)
            .padding(.vertical, 1)
            .background(color.opacity(0.18), in: Capsule())
            .foregroundStyle(color)
    }

    private var color: Color {
        switch level {
        case "high": return .green
        case "medium": return .orange
        default: return .gray
        }
    }
}

struct OpportunityRow: View {
    let chance: Opportunity

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("\(chance.playerName) (\(chance.team))").font(.body.weight(.semibold))
                Spacer()
                Text("\(chance.daysOut) d").font(.caption.bold()).foregroundStyle(.secondary)
            }
            ForEach(chance.gains.prefix(3)) { gain in
                HStack(spacing: 6) {
                    Text(gain.playerName).font(.callout).lineLimit(1)
                    Text(gain.ownerLabel).font(.caption2).foregroundStyle(tint(gain)).lineLimit(1)
                    Spacer()
                    if let now = gain.now, let bumped = gain.bumped {
                        Text("\(LineText.fmt(now.pts))→\(LineText.fmt(bumped.pts)) pts").font(.caption.monospacedDigit())
                    }
                    CertaintyBadge(level: gain.certainty.level)
                }
            }
        }
        .padding(.vertical, 2)
    }

    private func tint(_ gain: Gain) -> Color {
        switch gain.owner {
        case "mine": return .blue
        case "free", "unlisted": return .green
        default: return .secondary
        }
    }
}

struct OpportunityDetail: View {
    let chance: Opportunity
    let weakest: Weakest?
    let record: [String: TrackRecord]

    var body: some View {
        List {
            Section {
                InjuryRow(injury: Injury(
                    playerName: chance.playerName, status: chance.status, returnDate: chance.returnDate,
                    reported: chance.reported, part: chance.part, note: chance.note
                ))
                Text("He plays \(Int(chance.minutes.rounded())) min a game; out about \(chance.daysOut) days.").font(.caption).foregroundStyle(.secondary)
            }
            ForEach(chance.gains) { gain in
                Section {
                    BumpTable(now: gain.now, bumped: gain.bumped)
                    VStack(alignment: .leading, spacing: 3) {
                        if let now = gain.now?.min, let bumped = gain.bumped?.min {
                            Text("Expected now: \(signed(bumped - now)) min a game. History: \(LineText.fmt(gain.minWith)) min with him, \(LineText.fmt(gain.minWithout)) without (\(gain.gamesWithout) games); the pad trusts only part of that jump.")
                        }
                        if let past = record[gain.certainty.level] {
                            Text("Last season, \(gain.certainty.level) calls gained minutes \(Int((past.gained * 100).rounded()))% of the time, +\(LineText.fmt(past.minutes)) min on average (\(past.calls) calls).")
                        }
                        if gain.alreadyInLine >= 0.5 {
                            Text("He has mostly played without him already: most of this is in his line.")
                        }
                        if let beats = gain.beatsWeakest, let weakest {
                            Text(beats
                                 ? "Worth a look: beats your weakest, \(weakest.playerName) (\(LineText.fmt(weakest.value)))."
                                 : "Not better than your weakest, \(weakest.playerName) (\(LineText.fmt(weakest.value))).")
                                .foregroundStyle(beats ? .green : .secondary)
                        }
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                } header: {
                    HStack {
                        Text(gain.playerName)
                        Text("· \(gain.ownerLabel)")
                        Spacer()
                        CertaintyBadge(level: gain.certainty.level)
                    }
                }
            }
        }
        .navigationTitle(chance.playerName)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func signed(_ value: Double) -> String { (value >= 0 ? "+" : "") + LineText.fmt(value) }
}

/// Now vs with the bump, stat by stat, the change in colour.
struct BumpTable: View {
    let now: Line?
    let bumped: Line?

    var body: some View {
        if let now, let bumped {
            Grid(alignment: .trailing, horizontalSpacing: 10, verticalSpacing: 4) {
                GridRow {
                    Text("").gridColumnAlignment(.leading)
                    ForEach(Self.stats, id: \.0) { Text($0.0) }
                }
                .font(.caption2.bold())
                .foregroundStyle(.secondary)
                row("Now", now)
                row("Bumped", bumped)
                GridRow {
                    Text("Change").font(.caption2.bold()).foregroundStyle(.secondary)
                    ForEach(Self.stats, id: \.0) { stat in
                        let change = stat.1(bumped) - stat.1(now)
                        Text((change >= 0 ? "+" : "") + String(format: stat.0 == "VAL" ? "%.2f" : "%.1f", change))
                            .foregroundStyle(stat.0 == "TO" ? (change > 0.05 ? .red : .secondary) : (change > 0.05 ? .green : .secondary))
                    }
                }
            }
            .font(.caption.monospacedDigit())
        }
    }

    private func row(_ label: String, _ line: Line) -> some View {
        GridRow {
            Text(label).font(.caption2.bold()).foregroundStyle(.secondary)
            ForEach(Self.stats, id: \.0) { Text(String(format: $0.0 == "VAL" ? "%.2f" : "%.1f", $0.1(line))) }
        }
    }

    static let stats: [(String, (Line) -> Double)] = [
        ("MIN", { $0.min ?? 0 }), ("PTS", { $0.pts }), ("REB", { $0.reb }), ("AST", { $0.ast }),
        ("3PM", { $0.fg3m }), ("STL", { $0.stl }), ("BLK", { $0.blk }), ("TO", { $0.to ?? 0 }), ("VAL", { $0.value ?? 0 }),
    ]
}

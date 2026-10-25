import SwiftUI

/// Who is out, who gets his minutes, and what that does to their lines. Yours and pickups first.
struct NewsView: View {
    @Environment(FeedStore.self) private var store

    var body: some View {
        NavigationStack {
            List {
                if let news = store.feed?.news {
                    if !news.mineOut.isEmpty {
                        BrandSection("Your players out") {
                            ForEach(news.mineOut) { InjuryRow(injury: $0) }
                        }
                    }
                    if !news.opponentOut.isEmpty {
                        BrandSection("Opponent's players out") {
                            ForEach(news.opponentOut) { InjuryRow(injury: $0) }
                        }
                    }
                    BrandSection("Minutes opening up", footer: "From games with and without him, this season counted 3× last season. \"Likely free\" means he is on no roster you pasted: check Yahoo.") {
                        if news.opportunities.isEmpty { Text("No new absences").font(Theme.ui(15)).foregroundStyle(Theme.mute) }
                        ForEach(news.opportunities) { chance in
                            NavigationLink { OpportunityDetail(chance: chance, weakest: news.weakest, record: news.trackRecord) } label: { OpportunityRow(chance: chance) }
                        }
                    }
                } else {
                    ProgressView()
                }
            }
            .brandScreen("News")
            .refreshable { await store.refresh() }
        }
    }
}

struct InjuryRow: View {
    let injury: Injury

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 6) {
                Text(injury.playerName).font(Theme.ui(16, .semibold)).foregroundStyle(Theme.ink)
                Pill(text: injury.status, color: Theme.red)
                Spacer()
                if !injury.returnDate.isEmpty { Text("back ~\(Dates.short(injury.returnDate))").font(Theme.ui(12)).foregroundStyle(Theme.mute) }
            }
            if !injury.note.isEmpty { Text(injury.note).font(Theme.ui(12.5)).foregroundStyle(Theme.mute) }
        }
    }
}

struct OpportunityRow: View {
    let chance: Opportunity

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text("\(chance.playerName) (\(chance.team))").font(Theme.ui(16, .semibold)).foregroundStyle(Theme.ink)
                Spacer()
                Text("\(chance.daysOut) d").font(Theme.display(14)).foregroundStyle(Theme.mute)
            }
            ForEach(chance.gains.prefix(3)) { gain in
                HStack(spacing: 6) {
                    Text(gain.playerName).font(Theme.ui(14)).foregroundStyle(Theme.ink).lineLimit(1)
                    Text(gain.ownerLabel).font(Theme.ui(10.5, .medium)).foregroundStyle(Palette.owner(gain.owner)).lineLimit(1)
                    Spacer()
                    if let now = gain.now, let bumped = gain.bumped {
                        Text("\(LineText.fmt(now.pts))→\(LineText.fmt(bumped.pts)) pts").font(Theme.ui(12).monospacedDigit()).foregroundStyle(Theme.ink)
                    }
                    Pill(text: gain.certainty.level, color: Palette.certainty(gain.certainty.level))
                }
            }
        }
        .padding(.vertical, 2)
    }
}

struct OpportunityDetail: View {
    let chance: Opportunity
    let weakest: Weakest?
    let record: [String: TrackRecord]

    var body: some View {
        List {
            BrandSection {
                InjuryRow(injury: Injury(
                    playerName: chance.playerName, status: chance.status, returnDate: chance.returnDate,
                    reported: chance.reported, part: chance.part, note: chance.note
                ))
                Text("He plays \(Int(chance.minutes.rounded())) min a game; out about \(chance.daysOut) days.").font(Theme.ui(12.5)).foregroundStyle(Theme.mute)
            }
            ForEach(chance.gains) { gain in
                Section {
                    Group {
                        BumpTable(now: gain.now, bumped: gain.bumped)
                        notes(gain)
                    }
                    .listRowBackground(Theme.paper)
                } header: {
                    HStack(spacing: 6) {
                        SectionTitle(text: gain.playerName)
                        Text(gain.ownerLabel).font(Theme.ui(11, .medium)).foregroundStyle(Palette.owner(gain.owner))
                        Spacer()
                        Pill(text: gain.certainty.level, color: Palette.certainty(gain.certainty.level))
                    }
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(Theme.page)
        .navigationTitle(chance.playerName)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func notes(_ gain: Gain) -> some View {
        VStack(alignment: .leading, spacing: 4) {
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
                    .font(Theme.ui(12.5, beats ? .semibold : .regular))
                    .foregroundStyle(beats ? Theme.blue : Theme.mute)
            }
        }
        .font(Theme.ui(12.5))
        .foregroundStyle(Theme.mute)
    }

    private func signed(_ value: Double) -> String { (value >= 0 ? "+" : "") + LineText.fmt(value) }
}

/// Now vs with the bump, stat by stat, the change in colour.
struct BumpTable: View {
    let now: Line?
    let bumped: Line?

    var body: some View {
        if let now, let bumped {
            Grid(alignment: .trailing, horizontalSpacing: 9, verticalSpacing: 5) {
                GridRow {
                    Text("").gridColumnAlignment(.leading)
                    ForEach(Self.stats, id: \.0) { Text($0.0) }
                }
                .font(Theme.ui(10, .semibold))
                .foregroundStyle(Theme.mute)
                row("Now", now)
                row("Bumped", bumped)
                GridRow {
                    Text("Change").font(Theme.ui(10, .semibold)).foregroundStyle(Theme.mute)
                    ForEach(Self.stats, id: \.0) { stat in
                        let change = stat.1(bumped) - stat.1(now)
                        Text((change >= 0 ? "+" : "") + String(format: stat.0 == "VAL" ? "%.2f" : "%.1f", change))
                            .font(Theme.display(12.5).monospacedDigit())
                            .foregroundStyle(stat.0 == "TO" ? (change > 0.05 ? Theme.red : Theme.mute) : (change > 0.05 ? Theme.blue : Theme.mute))
                    }
                }
            }
            .font(Theme.ui(12).monospacedDigit())
            .foregroundStyle(Theme.ink)
        }
    }

    private func row(_ label: String, _ line: Line) -> some View {
        GridRow {
            Text(label).font(Theme.ui(10, .semibold)).foregroundStyle(Theme.mute)
            ForEach(Self.stats, id: \.0) { Text(String(format: $0.0 == "VAL" ? "%.2f" : "%.1f", $0.1(line))) }
        }
    }

    static let stats: [(String, (Line) -> Double)] = [
        ("MIN", { $0.min ?? 0 }), ("PTS", { $0.pts }), ("REB", { $0.reb }), ("AST", { $0.ast }),
        ("3PM", { $0.fg3m }), ("STL", { $0.stl }), ("BLK", { $0.blk }), ("TO", { $0.to ?? 0 }), ("VAL", { $0.value ?? 0 }),
    ]
}

import SwiftUI

/// Real numbers: this season's averages, the last five games and the next-game projection.
struct StatsView: View {
    @Environment(FeedStore.self) private var store
    @State private var side = 0

    var body: some View {
        NavigationStack {
            List {
                if let feed = store.feed {
                    Picker("Team", selection: $side) {
                        Text("Mine").tag(0)
                        Text(feed.opponent ?? "Opponent").tag(1)
                    }
                    .pickerStyle(.segmented)
                    .listRowBackground(Color.clear)
                    Section {
                        ForEach(side == 0 ? feed.mine : feed.theirs) { card in
                            NavigationLink { PlayerDetail(card: card) } label: { StatRow(card: card) }
                        }
                    } footer: {
                        Text("Per game this season. Tap a player for his last games and the pad's projection.")
                    }
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Stats")
            .refreshable { await store.refresh() }
        }
    }
}

private let columns = ["MIN", "PTS", "REB", "AST", "3PM", "STL", "BLK", "FG%"]

/// Name on its own line, then the numbers across the full width: seven columns beside a name do not fit a phone.
struct StatRow: View {
    let card: PlayerCard

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
                Text(card.playerName).font(.subheadline.weight(.semibold))
                if let injury = card.injury { Text(injury.status == "Out" ? "O" : "Q").font(.caption2.bold()).foregroundStyle(.red) }
                Spacer()
                Text("\(card.team) · \(card.positions) · \(card.season?.games ?? 0) g").font(.caption2).foregroundStyle(.secondary)
            }
            if let s = card.season {
                Grid(horizontalSpacing: 0, verticalSpacing: 1) {
                    GridRow { ForEach(columns, id: \.self) { Text($0).frame(maxWidth: .infinity) } }
                        .font(.system(size: 9.5, weight: .bold))
                        .foregroundStyle(.secondary)
                    GridRow {
                        ForEach(Array([s.min, s.pts, s.reb, s.ast, s.fg3m, s.stl, s.blk].enumerated()), id: \.offset) { Text(LineText.fmt($0.element)).frame(maxWidth: .infinity) }
                        Text(s.fgPct.map { String(format: "%.3f", $0) } ?? "—").frame(maxWidth: .infinity)
                    }
                    .font(.caption.monospacedDigit())
                }
            } else {
                Text("No games this season").font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 2)
    }
}

struct PlayerDetail: View {
    let card: PlayerCard

    var body: some View {
        List {
            if let injury = card.injury {
                Section("Injury") {
                    Text("\(injury.status)\(injury.returnDate.isEmpty ? "" : " · back ~\(Dates.short(injury.returnDate))")").foregroundStyle(.red)
                    if !injury.note.isEmpty { Text(injury.note).font(.caption).foregroundStyle(.secondary) }
                }
            }
            if let s = card.season {
                Section("This season · \(s.games) games") {
                    Grid(alignment: .trailing, horizontalSpacing: 14, verticalSpacing: 6) {
                        GridRow { label("MIN"); label("PTS"); label("REB"); label("AST"); label("3PM") }
                        GridRow { num(s.min); num(s.pts); num(s.reb); num(s.ast); num(s.fg3m) }
                        GridRow { label("STL"); label("BLK"); label("TO"); label("PF"); label("DD") }
                        GridRow { num(s.stl); num(s.blk); num(s.to); num(s.pf); Text("\(s.dd)") }
                        GridRow { label("FG"); label("FG%"); label("FT"); label("FT%"); Color.clear.frame(width: 1, height: 1) }
                        GridRow {
                            Text("\(LineText.fmt(s.fgm))/\(LineText.fmt(s.fga))")
                            Text(pct(s.fgPct))
                            Text("\(LineText.fmt(s.ftm))/\(LineText.fmt(s.fta))")
                            Text(pct(s.ftPct))
                            Color.clear.frame(width: 1, height: 1)
                        }
                    }
                    .font(.callout.monospacedDigit())
                }
            }
            if !card.recent.isEmpty {
                Section("Last games") {
                    ForEach(card.recent) { game in
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(Dates.short(game.date)) \(game.home ? "vs" : "@") \(game.opp)").font(.caption.bold())
                            Text("\(Int(game.min.rounded())) min · \(game.pts) pts · \(game.reb) reb · \(game.ast) ast · \(game.fg3m) 3s · \(game.stl) stl · \(game.blk) blk · \(game.to) to · \(game.fgm)/\(game.fga) FG")
                                .font(.caption.monospacedDigit())
                        }
                    }
                }
            }
            if let line = card.projection {
                Section {
                    Text(LineText.short(line)).font(.caption.monospacedDigit())
                    if let value = line.value { Text("12-cat value \(LineText.fmt(value))").font(.caption).foregroundStyle(.secondary) }
                } header: {
                    Text("Next game, pad projection")
                } footer: {
                    Text("Based on \(card.basis).")
                }
            }
        }
        .navigationTitle(card.playerName)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func label(_ text: String) -> some View { Text(text).font(.caption2.bold()).foregroundStyle(.secondary) }
    private func num(_ value: Double) -> some View { Text(LineText.fmt(value)) }
    private func pct(_ value: Double?) -> String { value.map { String(format: "%.3f", $0) } ?? "—" }
}

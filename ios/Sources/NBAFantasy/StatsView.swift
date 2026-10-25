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
                    BrandSection(side == 0 ? "Lipicaneri" : (feed.opponent ?? "Opponent"), footer: "Per game this season. Tap a player for his last games and the pad's projection.") {
                        ForEach(side == 0 ? feed.mine : feed.theirs) { card in
                            NavigationLink { PlayerDetail(card: card) } label: { StatRow(card: card) }
                        }
                    }
                } else {
                    ProgressView()
                }
            }
            .brandScreen("Stats")
            .refreshable { await store.refresh() }
        }
    }
}

private let columns = ["MIN", "PTS", "REB", "AST", "3PM", "STL", "BLK", "FG%"]

/// Name on its own line, then the numbers across the full width: seven columns beside a name do not fit a phone.
struct StatRow: View {
    let card: PlayerCard

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                Text(card.playerName).font(Theme.ui(15.5, .semibold)).foregroundStyle(Theme.ink)
                if let injury = card.injury { Pill(text: injury.status == "Out" ? "O" : "Q", color: Theme.red) }
                Spacer()
                Text("\(card.team) · \(card.positions) · \(card.season?.games ?? 0) g").font(Theme.ui(11)).foregroundStyle(Theme.mute)
            }
            if let s = card.season {
                Grid(horizontalSpacing: 0, verticalSpacing: 1) {
                    GridRow { ForEach(columns, id: \.self) { Text($0).frame(maxWidth: .infinity) } }
                        .font(Theme.ui(9.5, .semibold))
                        .foregroundStyle(Theme.mute)
                    GridRow {
                        ForEach(Array([s.min, s.pts, s.reb, s.ast, s.fg3m, s.stl, s.blk].enumerated()), id: \.offset) { Text(LineText.fmt($0.element)).frame(maxWidth: .infinity) }
                        Text(s.fgPct.map { String(format: "%.3f", $0) } ?? "—").frame(maxWidth: .infinity)
                    }
                    .font(Theme.display(14).monospacedDigit())
                    .foregroundStyle(Theme.ink)
                }
            } else {
                Text("No games this season").font(Theme.ui(12)).foregroundStyle(Theme.mute)
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
                BrandSection("Injury") {
                    Text("\(injury.status)\(injury.returnDate.isEmpty ? "" : " · back ~\(Dates.short(injury.returnDate))")").font(Theme.ui(15, .semibold)).foregroundStyle(Theme.red)
                    if !injury.note.isEmpty { Text(injury.note).font(Theme.ui(12.5)).foregroundStyle(Theme.mute) }
                }
            }
            if let s = card.season {
                BrandSection("This season · \(s.games) games") {
                    Grid(alignment: .trailing, horizontalSpacing: 16, verticalSpacing: 5) {
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
                    .font(Theme.display(17).monospacedDigit())
                    .foregroundStyle(Theme.ink)
                }
            }
            if !card.recent.isEmpty {
                BrandSection("Last games") {
                    ForEach(card.recent) { game in
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(Dates.short(game.date)) \(game.home ? "vs" : "@") \(game.opp)").font(Theme.ui(12.5, .semibold)).foregroundStyle(Theme.heading)
                            Text("\(Int(game.min.rounded())) min · \(game.pts) pts · \(game.reb) reb · \(game.ast) ast · \(game.fg3m) 3s · \(game.stl) stl · \(game.blk) blk · \(game.to) to · \(game.fgm)/\(game.fga) FG")
                                .font(Theme.ui(12).monospacedDigit())
                                .foregroundStyle(Theme.ink)
                        }
                    }
                }
            }
            if let line = card.projection {
                BrandSection("Next game, pad projection", footer: "Based on \(card.basis).") {
                    Text(LineText.short(line)).font(Theme.ui(12.5).monospacedDigit()).foregroundStyle(Theme.ink)
                    if let value = line.value { Text("12-cat value \(LineText.fmt(value))").font(Theme.ui(12)).foregroundStyle(Theme.mute) }
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(Theme.page)
        .navigationTitle(card.playerName)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func label(_ text: String) -> some View { Text(text).font(Theme.ui(10, .semibold)).foregroundStyle(Theme.mute) }
    private func num(_ value: Double) -> some View { Text(LineText.fmt(value)) }
    private func pct(_ value: Double?) -> String { value.map { String(format: "%.3f", $0) } ?? "—" }
}

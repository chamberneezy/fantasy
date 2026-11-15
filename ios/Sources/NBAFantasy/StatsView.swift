import SwiftUI

/// Rolling stats: my ten, my opponent's, and the league's top 50 by 12-cat value, over 7 days, 30 days or the season.
struct StatsView: View {
    @Environment(FeedStore.self) private var store
    @AppStorage("stats.view") private var view = "mine"
    @AppStorage("stats.window") private var window = "7d"
    @State private var sheet: PlayerCard?

    var body: some View {
        NavigationStack {
            List {
                if let feed = store.feed {
                    Section {
                        Picker("View", selection: $view) {
                            Text("Mine").tag("mine")
                            Text("Opponent").tag("theirs")
                            Text("League").tag("league")
                        }
                        .pickerStyle(.segmented)
                        if let board = feed.stats {
                            Picker("Window", selection: $window) {
                                ForEach(board.windows) { Text($0.label).tag($0.key) }
                            }
                            .pickerStyle(.segmented)
                        }
                    }
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                    if let board = feed.stats, let rows = board.rows[window] {
                        let shown = view == "league" ? rows.league : view == "theirs" ? rows.theirs : rows.mine
                        BrandSection(title(feed), footer: footer(board)) {
                            if shown.isEmpty { Text("No games in this window yet").font(Theme.ui(14)).foregroundStyle(Theme.mute) }
                            ForEach(shown) { row in
                                if let card = feed.cards?[row.playerName] ?? feed.card(row.playerName), card.games != nil {
                                    Button { sheet = card } label: {
                                        HStack {
                                            BoardRowView(row: row, showOwner: view == "league", headshot: (feed.cards?[row.playerName] ?? feed.card(row.playerName))?.headshot)
                                            Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(Theme.mute.opacity(0.6))
                                        }
                                        .contentShape(Rectangle())
                                    }
                                    .buttonStyle(.plain)
                                } else {
                                    NavigationLink {
                                        PlayerDetail(card: feed.cards?[row.playerName], row: row, windowLabel: label(board))
                                    } label: {
                                        BoardRowView(row: row, showOwner: view == "league", headshot: (feed.cards?[row.playerName] ?? feed.card(row.playerName))?.headshot)
                                    }
                                }
                            }
                        }
                    } else {
                        // A feed from before the board: season averages per player, as before.
                        BrandSection(view == "theirs" ? (feed.opponent ?? "Opponent") : (feed.team ?? "Lipicaneri")) {
                            ForEach(view == "theirs" ? feed.theirs : feed.mine) { card in
                                NavigationLink { PlayerDetail(card: card, row: nil, windowLabel: "Season") } label: { StatRow(card: card) }
                            }
                        }
                    }
                } else {
                    ProgressView()
                }
            }
            .brandScreen("Stats")
            .refreshable { await store.refresh() }
            .sheet(item: $sheet) { card in
                PlayerSheet(card: card, rank: store.feed?.seasonRank(card.playerName))
                    .presentationDragIndicator(.visible)
            }
        }
    }

    private func title(_ feed: Feed) -> String {
        switch view {
        case "league": return "League top 50 by value"
        case "theirs": return feed.opponent ?? "Opponent"
        default: return feed.team ?? "Lipicaneri"
        }
    }

    private func label(_ board: StatsBoard) -> String {
        board.windows.first { $0.key == window }?.label ?? "Season"
    }

    private func footer(_ board: StatsBoard) -> String {
        guard let current = board.windows.first(where: { $0.key == window }) else { return "" }
        var text = "Per game: points, rebounds, assists. Value = the 12-cat z-score sum of these averages. Tap a player for his card."
        if let from = current.from, let to = current.to { text += " Games \(Dates.short(from)) – \(Dates.short(to))." }
        if current.minGames > 1 { text += " Ranked with \(current.minGames)+ games." }
        return text
    }
}

private let columns = ["MIN", "PTS", "REB", "AST", "3PM", "STL", "BLK", "FG%"]

/// One player: rank, photo, name, three key numbers, and the 12-cat value large on the right.
struct BoardRowView: View {
    let row: BoardRow
    let showOwner: Bool
    var headshot: String? = nil

    var body: some View {
        HStack(spacing: 10) {
            Text(row.rank.map { "\($0)" } ?? "–").font(Theme.display(13)).foregroundStyle(Theme.mute).frame(width: 22, alignment: .leading)
            Headshot(url: headshot, size: 42, ring: ownerColor == Theme.mute ? Theme.mute.opacity(0.5) : ownerColor)
            VStack(alignment: .leading, spacing: 2) {
                Text(row.playerName).font(Theme.ui(15, .semibold)).foregroundStyle(Theme.ink).lineLimit(1).minimumScaleFactor(0.8)
                HStack(spacing: 4) {
                    Text("\(row.team) · \(row.positions)").foregroundStyle(Theme.mute)
                    if showOwner { Text(row.ownerLabel).foregroundStyle(ownerColor) }
                }
                .font(Theme.ui(11, .medium))
                .lineLimit(1)
            }
            Spacer(minLength: 4)
            MiniStat(value: row.pts, label: "PTS")
            MiniStat(value: row.reb, label: "REB")
            MiniStat(value: row.ast, label: "AST")
            VStack(spacing: 0) {
                Text(String(format: "%+.1f", row.value)).font(Theme.display(19).monospacedDigit()).foregroundStyle(row.value >= 0 ? Theme.blue : Theme.red)
                Text("VALUE").font(Theme.ui(8.5, .semibold)).kerning(0.6).foregroundStyle(Theme.mute)
            }
            .frame(width: 52, alignment: .trailing)
        }
        .padding(.vertical, 2)
        .opacity(row.fewGames == true ? 0.6 : 1)
    }

    /// Mine in blue, my opponent's in red, free agents in the heading colour, other teams muted.
    private var ownerColor: Color {
        switch row.owner {
        case "mine": return Theme.blue
        case "theirs": return Theme.red
        case "free": return Theme.heading
        default: return Theme.mute
        }
    }
}

private struct MiniStat: View {
    let value: Double
    let label: String

    var body: some View {
        VStack(spacing: 0) {
            Text(String(format: "%.1f", value)).font(Theme.display(14).monospacedDigit()).foregroundStyle(Theme.ink)
            Text(label).font(Theme.ui(8.5, .semibold)).foregroundStyle(Theme.mute)
        }
        .frame(width: 34)
    }
}

/// Season averages per player, for a feed without the board.
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

/// One player's page: the window's averages (from the board), injury, last games, next-game projection.
struct PlayerDetail: View {
    let card: PlayerCard?
    let row: BoardRow?
    let windowLabel: String

    var body: some View {
        List {
            if let injury = card?.injury {
                BrandSection("Injury") {
                    Text("\(injury.status)\(injury.returnDate.isEmpty ? "" : " · back ~\(Dates.short(injury.returnDate))")").font(Theme.ui(15, .semibold)).foregroundStyle(Theme.red)
                    if !injury.note.isEmpty { Text(injury.note).font(Theme.ui(12.5)).foregroundStyle(Theme.mute) }
                }
            }
            if let row {
                BrandSection("\(windowLabel) · \(row.games) games", footer: row.rank.map { "Rank \($0) in the league by value over this window." }) {
                    Grid(alignment: .trailing, horizontalSpacing: 16, verticalSpacing: 5) {
                        GridRow { label("MIN"); label("PTS"); label("REB"); label("AST"); label("3PM") }
                        GridRow { num(row.min); num(row.pts); num(row.reb); num(row.ast); num(row.fg3m) }
                        GridRow { label("STL"); label("BLK"); label("TO"); label("DD"); label("VALUE") }
                        GridRow { num(row.stl); num(row.blk); num(row.to); Text("\(row.dd)"); Text(String(format: "%.1f", row.value)).foregroundStyle(row.value >= 0 ? Theme.blue : Theme.red) }
                        GridRow { label("FG%"); label("FT%"); Color.clear.frame(width: 1, height: 1); Color.clear.frame(width: 1, height: 1); Color.clear.frame(width: 1, height: 1) }
                        GridRow { Text(pct(row.fgPct)); Text(pct(row.ftPct)); Color.clear.frame(width: 1, height: 1); Color.clear.frame(width: 1, height: 1); Color.clear.frame(width: 1, height: 1) }
                    }
                    .font(Theme.display(17).monospacedDigit())
                    .foregroundStyle(Theme.ink)
                }
            } else if let s = card?.season {
                BrandSection("This season · \(s.games) games") {
                    Grid(alignment: .trailing, horizontalSpacing: 16, verticalSpacing: 5) {
                        GridRow { label("MIN"); label("PTS"); label("REB"); label("AST"); label("3PM") }
                        GridRow { num(s.min); num(s.pts); num(s.reb); num(s.ast); num(s.fg3m) }
                        GridRow { label("STL"); label("BLK"); label("TO"); label("PF"); label("DD") }
                        GridRow { num(s.stl); num(s.blk); num(s.to); num(s.pf); Text("\(s.dd)") }
                    }
                    .font(Theme.display(17).monospacedDigit())
                    .foregroundStyle(Theme.ink)
                }
            }
            if let recent = card?.recent, !recent.isEmpty {
                BrandSection("Last games") {
                    ForEach(recent) { game in
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(Dates.short(game.date)) \(game.home ? "vs" : "@") \(game.opp)").font(Theme.ui(12.5, .semibold)).foregroundStyle(Theme.heading)
                            Text("\(Int(game.min.rounded())) min · \(game.pts) pts · \(game.reb) reb · \(game.ast) ast · \(game.fg3m) 3s · \(game.stl) stl · \(game.blk) blk · \(game.to) to · \(game.fgm)/\(game.fga) FG")
                                .font(Theme.ui(12).monospacedDigit())
                                .foregroundStyle(Theme.ink)
                        }
                    }
                }
            }
            if let card, let line = card.projection {
                BrandSection("Next game, pad projection", footer: "Based on \(card.basis).") {
                    Text(LineText.short(line)).font(Theme.ui(12.5).monospacedDigit()).foregroundStyle(Theme.ink)
                    if let value = line.value { Text("12-cat value \(LineText.fmt(value))").font(Theme.ui(12)).foregroundStyle(Theme.mute) }
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(Theme.page)
        .navigationTitle(row?.playerName ?? card?.playerName ?? "")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func label(_ text: String) -> some View { Text(text).font(Theme.ui(10, .semibold)).foregroundStyle(Theme.mute) }
    private func num(_ value: Double) -> some View { Text(LineText.fmt(value)) }
    private func pct(_ value: Double?) -> String { value.map { String(format: "%.3f", $0) } ?? "—" }
}

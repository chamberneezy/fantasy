import SwiftUI

/// The player sheet from the court: one game at a time (last five to pick from), then his season.
struct PlayerSheet: View {
    let card: PlayerCard
    let rank: Int?
    @State private var picked = 0
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                PlayerHeader(card: card, rank: rank) { dismiss() }
                Group {
                    if let games = card.games, !games.isEmpty {
                        GamePicker(games: games, picked: $picked)
                        GameCardView(game: games[min(picked, games.count - 1)])
                    } else {
                        Panel { Text("No games this season yet").font(Theme.ui(14)).foregroundStyle(Theme.mute) }
                    }
                    if let season = card.season {
                        Panel(title: "Season averages · \(season.games) games") { SeasonGrid(season: season, ts: card.seasonTsPct) }
                    }
                    if let value = card.seasonValue {
                        Panel(title: "Season · 12-cat value per game") {
                            ValueBars(value: value, caption: seasonCaption)
                        }
                    }
                }
                .padding(.horizontal, 16)
            }
            .padding(.bottom, 24)
        }
        .ignoresSafeArea(edges: .top)
        .background(Theme.page)
    }

    private var seasonCaption: String {
        var text = "Sum \(Fmt.signed(card.seasonValue?.value ?? 0))"
        if let rank { text += " · league rank \(rank)" }
        return text
    }
}

/// Photo on the brand gradient, edge to edge at the top of the sheet, with the close button top right.
struct PlayerHeader: View {
    let card: PlayerCard
    let rank: Int?
    let close: () -> Void

    var body: some View {
        HStack(spacing: 16) {
            Headshot(url: card.headshot, size: 108, ring: .white.opacity(0.9))
            VStack(alignment: .leading, spacing: 5) {
                Text(card.playerName.uppercased()).font(Theme.display(28)).kerning(0.6).foregroundStyle(.white).lineLimit(2).minimumScaleFactor(0.7)
                Text("\(card.team) · \(card.positions)").font(Theme.ui(14, .medium)).foregroundStyle(.white.opacity(0.85))
                HStack(spacing: 6) {
                    if let value = card.seasonValue {
                        Tag(text: "Value \(Fmt.signed(value.value))", color: value.value >= 0 ? Theme.blue : Theme.red)
                    }
                    if let rank { Tag(text: "Rank \(rank)", color: Color(hex: 0x1D428A)) }
                    if let injury = card.injury, !injury.status.isEmpty { Tag(text: injury.status, color: Theme.red) }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 20)
        .padding(.top, 52)
        .padding(.bottom, 24)
        .frame(maxWidth: .infinity)
        .background(
            LinearGradient(colors: [Color(hex: 0x1D428A), Theme.blue, Theme.red.opacity(0.85)], startPoint: .topLeading, endPoint: .bottomTrailing),
            in: UnevenRoundedRectangle(bottomLeadingRadius: 24, bottomTrailingRadius: 24)
        )
        .overlay(alignment: .topTrailing) {
            Button(action: close) {
                Image(systemName: "xmark")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(width: 34, height: 34)
                    .background(.black.opacity(0.28), in: Circle())
                    .overlay(Circle().stroke(.white.opacity(0.35), lineWidth: 1))
            }
            .buttonStyle(.plain)
            .padding(.top, 16)
            .padding(.trailing, 16)
            .accessibilityLabel("Close")
        }
    }
}

private struct Tag: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text).font(Theme.ui(11, .semibold)).foregroundStyle(.white)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(color, in: Capsule())
            .overlay(Capsule().stroke(.white.opacity(0.35), lineWidth: 1))
    }
}

/// The last five games as chips, newest first.
struct GamePicker: View {
    let games: [GameCard]
    @Binding var picked: Int

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(Array(games.enumerated()), id: \.offset) { index, game in
                    Button { picked = index } label: {
                        VStack(spacing: 1) {
                            Text(Dates.short(game.date)).font(Theme.ui(11, .semibold))
                            Text("\(game.home ? "vs" : "@") \(game.opp)").font(Theme.display(13))
                        }
                        .padding(.horizontal, 12).padding(.vertical, 6)
                        .foregroundStyle(index == picked ? .white : Theme.ink)
                        .background(index == picked ? Theme.blue : Theme.paper, in: RoundedRectangle(cornerRadius: 10))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}

/// One game: result, the line, points by quarter, shot chart, efficiency, 12-cat value.
struct GameCardView: View {
    let game: GameCard

    var body: some View {
        VStack(spacing: 14) {
            Panel {
                VStack(spacing: 12) {
                    HStack {
                        Text(resultText).font(Theme.display(15)).foregroundStyle(resultColor)
                        Spacer()
                        Text("\(Dates.short(game.date)) · \(Int(game.min.rounded())) min").font(Theme.ui(12.5)).foregroundStyle(Theme.mute)
                    }
                    HStack(spacing: 0) {
                        BigStat(value: game.pts, label: "PTS")
                        BigStat(value: game.reb, label: "REB")
                        BigStat(value: game.ast, label: "AST")
                    }
                    StatGrid(items: [
                        ("FG", "\(game.fgm)/\(game.fga)"),
                        ("3PT", game.fg3a.map { "\(game.fg3m)/\($0)" } ?? "\(game.fg3m)"),
                        ("FT", "\(game.ftm)/\(game.fta)"),
                        ("STL", "\(game.stl)"),
                        ("BLK", "\(game.blk)"),
                        ("TO", "\(game.to)"),
                        ("PF", "\(game.pf)"),
                        ("DD", game.dd > 0 ? "Yes" : "–"),
                    ])
                }
            }
            if let shots = game.shots {
                Panel(title: "Shot chart · \(game.fgm)/\(game.fga) FG") { ShotChart(shots: shots) }
            }
            if let quarters = game.quarters {
                Panel(title: "Points by quarter") { QuarterBars(quarters: quarters) }
            }
            Panel(title: "Efficiency") {
                VStack(spacing: 16) {
                    HStack(spacing: 12) {
                        Gauge(label: "TS%", text: game.tsPct.map { String(format: "%.1f", $0 * 100) }, fraction: (game.tsPct ?? 0) / 0.8, note: "points per shot")
                        Gauge(label: "USG%", text: game.usgPct.map { String(format: "%.1f", $0 * 100) }, fraction: (game.usgPct ?? 0) / 0.4, note: "team plays used")
                    }
                    HStack(spacing: 12) {
                        Gauge(label: "GAME SCORE", text: game.gameScore.map { String(format: "%.1f", $0) }, fraction: (game.gameScore ?? 0) / 40, note: "10 average · 20 good · 30+ great")
                        Gauge(
                            label: "+/-",
                            text: game.plusMinus.map { $0 > 0 ? "+\($0)" : "\($0)" },
                            fraction: Double(abs(game.plusMinus ?? 0)) / 30,
                            note: "team margin with him on",
                            tint: (game.plusMinus ?? 0) < 0 ? Theme.red : Theme.blue
                        )
                    }
                }
            }
            Panel(title: "12-cat value this game") {
                ValueBars(value: CatValue(z: game.z, value: game.value), caption: "Sum \(Fmt.signed(game.value)) against the season's per-game pool")
            }
        }
    }

    private var resultText: String {
        let place = "\(game.home ? "vs" : "@") \(game.opp)"
        guard let score = game.score else { return place }
        return "\(score.won ? "W" : "L") \(score.team)–\(score.opp) \(place)"
    }

    private var resultColor: Color {
        guard let score = game.score else { return Theme.heading }
        return score.won ? Theme.blue : Theme.red
    }
}

/// A rounded card on the paper colour with an optional section title.
struct Panel<Content: View>: View {
    var title: String? = nil
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let title { SectionTitle(text: title) }
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Theme.paper, in: RoundedRectangle(cornerRadius: 16))
    }
}

private struct BigStat: View {
    let value: Int
    let label: String

    var body: some View {
        VStack(spacing: 0) {
            Text("\(value)").font(Theme.display(44).monospacedDigit()).foregroundStyle(Theme.heading)
            Text(label).font(Theme.ui(11, .semibold)).kerning(1).foregroundStyle(Theme.mute)
        }
        .frame(maxWidth: .infinity)
    }
}

private struct StatGrid: View {
    let items: [(String, String)]

    var body: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 4), spacing: 8) {
            ForEach(items, id: \.0) { item in
                VStack(spacing: 1) {
                    Text(item.1).font(Theme.display(17).monospacedDigit()).foregroundStyle(Theme.ink)
                    Text(item.0).font(Theme.ui(10.5, .semibold)).foregroundStyle(Theme.mute)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
                .background(Theme.page, in: RoundedRectangle(cornerRadius: 8))
            }
        }
    }
}

/// Q1–Q4 (and overtimes) as bars, the points above each.
struct QuarterBars: View {
    let quarters: [Int]

    var body: some View {
        let top = max(quarters.max() ?? 1, 1)
        HStack(alignment: .bottom, spacing: 10) {
            ForEach(Array(quarters.enumerated()), id: \.offset) { index, points in
                VStack(spacing: 4) {
                    Text("\(points)").font(Theme.display(15).monospacedDigit()).foregroundStyle(points == top && points > 0 ? Theme.blue : Theme.ink)
                    RoundedRectangle(cornerRadius: 5)
                        .fill(points == top && points > 0 ? Theme.blue : Theme.blue.opacity(0.35))
                        .frame(height: max(4, CGFloat(points) / CGFloat(top) * 80))
                    Text(index < 4 ? "Q\(index + 1)" : "OT\(index - 3 > 1 ? "\(index - 3)" : "")").font(Theme.ui(11, .semibold)).foregroundStyle(Theme.mute)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .frame(height: 124, alignment: .bottom)
    }
}

/// Makes as filled blue dots, misses as red crosses, on the half court.
struct ShotChart: View {
    let shots: [[Double]]

    var body: some View {
        VStack(spacing: 8) {
            CourtFloor()
                .overlay {
                    GeometryReader { geo in
                        let rect = CGRect(origin: .zero, size: geo.size)
                        let dot = max(7, rect.width / 38)
                        ForEach(Array(shots.enumerated()), id: \.offset) { _, shot in
                            if shot.count >= 3 {
                                let point = CourtGeometry.shot(x: shot[0], y: shot[1], in: rect)
                                if shot[2] > 0 {
                                    Circle().fill(Theme.blue).overlay(Circle().stroke(.white, lineWidth: 1.2))
                                        .frame(width: dot, height: dot).position(point)
                                } else {
                                    Image(systemName: "xmark").font(.system(size: dot * 0.9, weight: .heavy)).foregroundStyle(Theme.red)
                                        .position(point)
                                }
                            }
                        }
                    }
                }
            HStack(spacing: 14) {
                Label("Made", systemImage: "circle.fill").foregroundStyle(Theme.blue)
                Label("Missed", systemImage: "xmark").foregroundStyle(Theme.red)
            }
            .font(Theme.ui(11.5, .medium))
        }
    }
}

/// A ring filled to `value / scale`, the percentage in the middle.
private struct Gauge: View {
    let label: String
    let text: String?
    let fraction: Double
    let note: String
    /// One colour for a signed number (plus-minus); the brand blue→red sweep otherwise.
    var tint: Color? = nil

    var body: some View {
        VStack(spacing: 6) {
            ZStack {
                Circle().stroke(Theme.blue.opacity(0.15), lineWidth: 9)
                Circle()
                    .trim(from: 0, to: max(0, min(1, fraction)))
                    .stroke(
                        tint.map { AnyShapeStyle($0) } ?? AnyShapeStyle(AngularGradient(colors: [Theme.blue, Theme.red], center: .center)),
                        style: StrokeStyle(lineWidth: 9, lineCap: .round)
                    )
                    .rotationEffect(.degrees(-90))
                Text(text ?? "–").font(Theme.display(22).monospacedDigit()).foregroundStyle(tint ?? Theme.heading)
            }
            .frame(width: 92, height: 92)
            Text(label).font(Theme.display(13)).kerning(1).foregroundStyle(Theme.ink)
            Text(note).font(Theme.ui(10.5)).foregroundStyle(Theme.mute).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
    }
}

/// The 12 categories as bars left (hurts) or right (helps) of zero, then the sum.
struct ValueBars: View {
    let value: CatValue
    let caption: String

    static let order = ["MIN", "FG%", "FT%", "3PM", "PTS", "REB", "AST", "STL", "BLK", "TO", "PF", "DD"]

    var body: some View {
        VStack(spacing: 5) {
            HStack(alignment: .firstTextBaseline) {
                Text(Fmt.signed(value.value)).font(Theme.display(34).monospacedDigit()).foregroundStyle(value.value >= 0 ? Theme.blue : Theme.red)
                Text("12-cat sum").font(Theme.ui(12, .medium)).foregroundStyle(Theme.mute)
                Spacer()
            }
            ForEach(Self.order, id: \.self) { cat in
                let z = value.z[cat] ?? 0
                HStack(spacing: 8) {
                    Text(cat).font(Theme.ui(11.5, .semibold)).foregroundStyle(Theme.ink).frame(width: 36, alignment: .leading)
                    GeometryReader { geo in
                        let half = geo.size.width / 2
                        let length = min(half, CGFloat(abs(z)) / 3 * half)
                        ZStack(alignment: .leading) {
                            Rectangle().fill(Theme.mute.opacity(0.25)).frame(width: 1).offset(x: half)
                            RoundedRectangle(cornerRadius: 3)
                                .fill(z >= 0 ? Theme.blue : Theme.red)
                                .frame(width: max(2, length), height: 10)
                                .offset(x: z >= 0 ? half : half - length)
                        }
                        .frame(height: geo.size.height)
                    }
                    .frame(height: 14)
                    Text(Fmt.signed(z)).font(Theme.ui(11.5).monospacedDigit()).foregroundStyle(z >= 0 ? Theme.blue : Theme.red).frame(width: 40, alignment: .trailing)
                }
            }
            Text(caption).font(Theme.ui(11)).foregroundStyle(Theme.mute).frame(maxWidth: .infinity, alignment: .leading).padding(.top, 2)
        }
    }
}

private struct SeasonGrid: View {
    let season: Average
    let ts: Double?

    var body: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 4), spacing: 8) {
            ForEach(items, id: \.0) { item in
                VStack(spacing: 1) {
                    Text(item.1).font(Theme.display(16).monospacedDigit()).foregroundStyle(Theme.ink)
                    Text(item.0).font(Theme.ui(10.5, .semibold)).foregroundStyle(Theme.mute)
                }
                .frame(maxWidth: .infinity)
            }
        }
    }

    private var items: [(String, String)] {
        [
            ("MIN", Fmt.one(season.min)), ("PTS", Fmt.one(season.pts)), ("REB", Fmt.one(season.reb)), ("AST", Fmt.one(season.ast)),
            ("3PM", Fmt.one(season.fg3m)), ("STL", Fmt.one(season.stl)), ("BLK", Fmt.one(season.blk)), ("TO", Fmt.one(season.to)),
            ("FG%", Fmt.pct(season.fgPct)), ("FT%", Fmt.pct(season.ftPct)), ("TS%", Fmt.pct(ts)), ("DD", "\(season.dd)"),
        ]
    }
}

enum Fmt {
    static func signed(_ value: Double) -> String { String(format: "%+.1f", value) }
    static func one(_ value: Double) -> String { String(format: "%.1f", value) }
    /// ".513", and "1.000" for a perfect night.
    static func pct(_ value: Double?) -> String {
        guard let value else { return "–" }
        return value >= 1 ? "1.000" : String(format: ".%03d", Int((value * 1000).rounded()))
    }
}

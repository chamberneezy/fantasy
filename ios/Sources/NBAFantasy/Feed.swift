import Foundation

/// `app.json` from the laptop pad (scripts/export_season.py → GitHub Pages).
struct Feed: Codable {
    let version: Int
    let publishedAt: String
    let logsThrough: String?
    let week: Int
    let weekStart: String
    let weekEnd: String
    let opponent: String?
    let addsLeft: Int?
    let today: Today
    let days: [Day]
    let leans: [Lean]
    let score: Score?
    let season: [SeasonWeek]?
    let yahooThrough: String?
    let leansNote: String
    let news: News
    let mine: [PlayerCard]
    let theirs: [PlayerCard]
    let stats: StatsBoard?
    let cards: [String: PlayerCard]?
    let recap: Recap?
    let injuries: InjuryLists?
    /// Today's seats as Yahoo has them (feed version 3 on).
    let lineup: Lineup?
    let team: String?

    /// My card for a name: my ten and IL first, then the shared cards.
    func card(_ name: String) -> PlayerCard? {
        mine.first { $0.playerName == name } ?? cards?[name]
    }

    /// Season rank by 12-cat value, from the stats board.
    func seasonRank(_ name: String) -> Int? {
        guard let rows = stats?.rows["season"] else { return nil }
        return (rows.mine + rows.theirs + rows.league).first { $0.playerName == name }?.rank
    }

    static let url = URL(string: "https://chamberneezy.github.io/fantasy/data/season/app.json")!

    static func decode(_ data: Data) throws -> Feed {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Feed.self, from: data)
    }
}

struct Today: Codable {
    let date: String
    let starters: [Game]
    let bench: [Game]
    let off: [String]
}

struct Game: Codable, Identifiable {
    var id: String { playerName }
    let playerName: String
    let positions: String
    let team: String
    let seat: String?
    let opp: String
    let home: Bool
    let tipUtc: String?
    let status: String
    let chance: Double?
    let line: Line?
}

/// Per-game line. News and stat lines also carry the percentages and the 12-cat value.
struct Line: Codable {
    let min: Double?
    let pts: Double
    let reb: Double
    let ast: Double
    let fg3m: Double
    let stl: Double
    let blk: Double
    let to: Double?
    let fgPct: Double?
    let ftPct: Double?
    let value: Double?
}

struct Day: Codable, Identifiable {
    var id: String { date }
    let date: String
    let dow: String
    let past: Bool
    let myStarts: Int
    let myPlayers: Int
    let theirPlayers: Int
}

struct Lean: Codable, Identifiable {
    var id: String { cat }
    let cat: String
    let mine: Double
    let theirs: Double
    let lean: String
    let yahooMine: Double?
    let yahooTheirs: Double?
}

struct News: Codable {
    let mineOut: [Injury]
    let opponentOut: [Injury]
    let opportunities: [Opportunity]
    let weakest: Weakest?
    let trackRecord: [String: TrackRecord]
}

/// How calls at one certainty level did when last season was replayed.
struct TrackRecord: Codable {
    let gained: Double
    let gained3: Double
    let minutes: Double
    let calls: Int
}

/// The week as Yahoo scores it (categories won / lost / tied through a day) and the outlook as lean counts.
struct Score: Codable {
    let through: String?
    let won: Int?
    let lost: Int?
    let tied: Int?
    let outlook: Outlook
    /// Where the score comes from, e.g. "Yahoo to Fri 23 Oct + box scores to Sat 24 Oct".
    let basis: String?

    var text: String? {
        guard let won, let lost, let tied else { return nil }
        return tied > 0 ? "\(won)–\(lost)–\(tied)" : "\(won)–\(lost)"
    }
}

struct Outlook: Codable {
    let yours: Int
    let coinFlip: Int
    let his: Int
}

/// One week of the season: opponent, and Yahoo's score once one is on file.
struct SeasonWeek: Codable, Identifiable {
    var id: Int { week }
    let week: Int
    let start: String
    let end: String
    let opponent: String
    let current: Bool
    let through: String?
    let won: Int?
    let lost: Int?
    let tied: Int?
    let final: Bool?

    var scoreText: String? {
        guard let won, let lost, let tied else { return nil }
        return tied > 0 ? "\(won)–\(lost)–\(tied)" : "\(won)–\(lost)"
    }

    /// Won, lost or tied the week, once it is final.
    var outcome: String? {
        guard final == true, let won, let lost else { return nil }
        return won > lost ? "W" : won < lost ? "L" : "T"
    }
}

/// Mario's lowest-value player who is not protected: the bar a pickup must clear.
struct Weakest: Codable {
    let playerName: String
    let value: Double
}

struct Injury: Codable, Identifiable {
    var id: String { playerName + reported }
    let playerName: String
    let status: String
    let returnDate: String
    let reported: String
    let part: String?
    let note: String
}

/// Every injury on both rosters, not only the ones ruled out.
struct InjuryLists: Codable {
    let mine: [Injury]
    let theirs: [Injury]
}

/// Last night: both teams' starters, who won the night by category, the week after it.
struct Recap: Codable {
    let date: String
    let played: Bool
    let week: Int?
    let opponent: String?
    let mine: [RecapLine]
    let theirs: [RecapLine]
    let night: Tally?
    let weekScore: Tally?
}

struct RecapLine: Codable, Identifiable {
    var id: String { playerName }
    let playerName: String
    let mp: Double
    let pts: Double
    let reb: Double
    let ast: Double
    let fg3m: Double
    let stl: Double
    let blk: Double
    let to: Double
    let fgm: Double
    let fga: Double

    /// "32 pts · 6 reb · 8 ast · 3 3s": the counting stats that matter, zeros left out after points.
    var short: String {
        var parts = ["\(Int(pts)) pts"]
        if reb > 0 { parts.append("\(Int(reb)) reb") }
        if ast > 0 { parts.append("\(Int(ast)) ast") }
        if fg3m > 0 { parts.append("\(Int(fg3m)) 3s") }
        if stl > 0 { parts.append("\(Int(stl)) stl") }
        if blk > 0 { parts.append("\(Int(blk)) blk") }
        return parts.joined(separator: " · ")
    }
}

struct Tally: Codable {
    let won: Int
    let lost: Int
    let tied: Int

    var text: String { tied > 0 ? "\(won)–\(lost)–\(tied)" : "\(won)–\(lost)" }
}

struct Opportunity: Codable, Identifiable {
    var id: String { playerName + reported }
    let playerName: String
    let status: String
    let returnDate: String
    let reported: String
    let part: String
    let note: String
    let team: String
    let minutes: Double
    let daysOut: Int
    let gains: [Gain]

    /// A gain Mario can use: his own player, or someone he can pick up.
    var usable: [Gain] { gains.filter { $0.owner == "mine" || $0.owner == "free" || $0.owner == "unlisted" } }
}

struct Gain: Codable, Identifiable {
    var id: String { playerName }
    let playerName: String
    let owner: String
    let yahooStatus: String
    let minWith: Double
    let minWithout: Double
    let gamesWithout: Int
    let certainty: Certainty
    let alreadyInLine: Double
    let now: Line?
    let bumped: Line?
    let beatsWeakest: Bool?

    var ownerLabel: String {
        switch owner {
        case "mine": return "Yours"
        case "free": return "Free agent"
        case "unlisted": return "Likely free, check Yahoo"
        default: return owner
        }
    }
}

/// How sure the minutes jump is, and its range (minutes per game).
struct Certainty: Codable {
    let level: String
    let t: Double
    let gainLow: Double
    let gainHigh: Double
}

struct PlayerCard: Codable, Identifiable {
    var id: String { playerName }
    let playerName: String
    let headshot: String?
    let team: String
    let positions: String
    let injury: CardInjury?
    let season: Average?
    let recent: [GameLine]
    let projection: Line?
    let basis: String
    /// My players only: the last games as full cards, the season's 12-cat value and TS%.
    let games: [GameCard]?
    let seasonValue: CatValue?
    let seasonTsPct: Double?
}

/// 12 z-scores against the season pool, and their plain sum.
struct CatValue: Codable {
    let z: [String: Double]
    let value: Double
}

/// One game as the player card shows it.
struct GameCard: Codable, Identifiable {
    var id: String { gameId }
    let gameId: String
    let date: String
    let opp: String
    let home: Bool
    let min: Double
    let fgm: Int
    let fga: Int
    let ftm: Int
    let fta: Int
    let fg3m: Int
    let fg3a: Int?
    let pts: Int
    let reb: Int
    let ast: Int
    let stl: Int
    let blk: Int
    let to: Int
    let pf: Int
    let dd: Int
    let tsPct: Double?
    let usgPct: Double?
    /// Hollinger's Game Score and the team's margin with him on the floor.
    let gameScore: Double?
    let plusMinus: Int?
    /// Points per quarter (overtimes after the fourth).
    let quarters: [Int]?
    /// [x, y, made, value]: feet, x 0–50 across, y from the rim.
    let shots: [[Double]]?
    let z: [String: Double]
    let value: Double
    let score: GameScore?
}

struct GameScore: Codable {
    let team: Int
    let opp: Int
    let won: Bool
}

struct Lineup: Codable {
    let date: String
    let court: [Spot]
    let bench: [Spot]
    let il: [Spot]
}

/// One seat: who sits in it, his photo, tonight's game.
struct Spot: Codable, Identifiable {
    var id: String { slot + (playerName ?? "") }
    let slot: String
    let playerName: String?
    let shortName: String?
    let headshot: String?
    let team: String?
    let positions: String?
    let opp: String?
    let home: Bool?
    let tipUtc: String?
    let status: String?

    var plays: Bool { opp != nil }
}

struct CardInjury: Codable {
    let status: String
    let returnDate: String
    let note: String
}

struct Average: Codable {
    let min: Double
    let fgm: Double
    let fga: Double
    let ftm: Double
    let fta: Double
    let fg3m: Double
    let pts: Double
    let reb: Double
    let ast: Double
    let stl: Double
    let blk: Double
    let to: Double
    let pf: Double
    let dd: Int
    let fgPct: Double?
    let ftPct: Double?
    let games: Int
}

struct GameLine: Codable, Identifiable {
    var id: String { date }
    let date: String
    let opp: String
    let home: Bool
    let min: Double
    let fgm: Int
    let fga: Int
    let ftm: Int
    let fta: Int
    let fg3m: Int
    let pts: Int
    let reb: Int
    let ast: Int
    let stl: Int
    let blk: Int
    let to: Int
    let pf: Int
    let dd: Int
}

enum Dates {
    /// "2026-10-27" → "Tue 27 Oct".
    static func short(_ iso: String) -> String {
        let parser = DateFormatter()
        parser.dateFormat = "yyyy-MM-dd"
        parser.locale = Locale(identifier: "en_US_POSIX")
        guard let date = parser.date(from: iso) else { return iso }
        let out = DateFormatter()
        out.dateFormat = "EEE d MMM"
        out.locale = Locale(identifier: "en_GB")
        return out.string(from: date)
    }

    /// A date as "2026-10-27", the feed's format, so feed dates compare as text.
    static func iso(_ date: Date) -> String {
        let out = DateFormatter()
        out.dateFormat = "yyyy-MM-dd"
        out.locale = Locale(identifier: "en_US_POSIX")
        return out.string(from: date)
    }
}

/// Rolling stats: per window (7 days, 30 days, season), the league's top players by value and both teams.
struct StatsBoard: Codable {
    let windows: [StatsWindow]
    let rows: [String: BoardRows]
}

struct StatsWindow: Codable, Identifiable {
    var id: String { key }
    let key: String
    let label: String
    let from: String?
    let to: String?
    let minGames: Int
}

struct BoardRows: Codable {
    let league: [BoardRow]
    let mine: [BoardRow]
    let theirs: [BoardRow]
}

struct BoardRow: Codable, Identifiable {
    var id: String { playerName }
    let playerName: String
    let team: String
    let positions: String
    let owner: String
    let games: Int
    let min: Double
    let pts: Double
    let reb: Double
    let ast: Double
    let fg3m: Double
    let stl: Double
    let blk: Double
    let to: Double
    let fgPct: Double?
    let ftPct: Double?
    let dd: Int
    let value: Double
    let rank: Int?
    let fewGames: Bool?

    var ownerLabel: String {
        switch owner {
        case "mine": return "Yours"
        case "theirs": return "Opponent"
        case "free": return "Free agent"
        default: return owner
        }
    }
}

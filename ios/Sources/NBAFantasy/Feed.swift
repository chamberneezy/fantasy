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
    let yahooThrough: String?
    let leansNote: String
    let news: News
    let mine: [PlayerCard]
    let theirs: [PlayerCard]

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
    let part: String
    let note: String
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
    let team: String
    let positions: String
    let injury: CardInjury?
    let season: Average?
    let recent: [GameLine]
    let projection: Line?
    let basis: String
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
}

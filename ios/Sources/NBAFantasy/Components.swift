import SwiftUI

/// A list section in the site's style: Oswald header, rows on the paper colour, optional footer.
struct BrandSection<Content: View>: View {
    let title: String?
    let footer: String?
    @ViewBuilder let content: () -> Content

    init(_ title: String? = nil, footer: String? = nil, @ViewBuilder content: @escaping () -> Content) {
        self.title = title
        self.footer = footer
        self.content = content
    }

    var body: some View {
        Section {
            content().listRowBackground(Theme.paper)
        } header: {
            if let title { SectionTitle(text: title) }
        } footer: {
            if let footer { Text(footer).font(Theme.ui(12)).foregroundStyle(Theme.mute) }
        }
    }
}

/// A small coloured capsule: lean words, certainty, status.
struct Pill: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(Theme.ui(11, .semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color.opacity(0.16), in: Capsule())
            .foregroundStyle(color)
    }
}

enum Palette {
    /// Lean words: blue for my side, gold for a coin flip, red for his.
    static func lean(_ word: String) -> Color {
        switch word {
        case "likely yours": return Theme.blue
        case "lean yours": return Theme.blue.opacity(0.75)
        case "coin flip": return Color(hex: 0xC99A0E)
        case "lean his": return Theme.red.opacity(0.8)
        default: return Theme.red
        }
    }

    static func certainty(_ level: String) -> Color {
        switch level {
        case "high": return Theme.blue
        case "medium": return Color(hex: 0xC99A0E)
        default: return Theme.mute
        }
    }

    /// Mine in blue; players I could add in the heading colour; other teams muted.
    static func owner(_ owner: String) -> Color {
        switch owner {
        case "mine": return Theme.blue
        case "free", "unlisted": return Theme.heading
        default: return Theme.mute
        }
    }
}

/// This week's score in the brand type: Yahoo's real categories, then the outlook in words.
struct ScoreCard: View {
    let feed: Feed

    var body: some View {
        VStack(spacing: 8) {
            HStack(alignment: .center) {
                Text("LIPICANERI").font(Theme.display(13)).kerning(1).foregroundStyle(Theme.blue)
                Spacer()
                Text((feed.opponent ?? "Opponent").uppercased()).font(Theme.display(13)).kerning(1).foregroundStyle(Theme.red).lineLimit(1)
            }
            if let score = feed.score, let won = score.won, let lost = score.lost, let tied = score.tied {
                HStack(spacing: 10) {
                    Text("\(won)").foregroundStyle(won >= lost ? Theme.blue : Theme.ink)
                    Text("–").foregroundStyle(Theme.mute)
                    Text("\(lost)").foregroundStyle(lost > won ? Theme.red : Theme.ink)
                    if tied > 0 {
                        Text("–").foregroundStyle(Theme.mute)
                        Text("\(tied)").foregroundStyle(Theme.mute)
                    }
                }
                .font(Theme.display(44).monospacedDigit())
                Text(score.basis ?? "Through \(score.through.map(Dates.short) ?? "—")")
                    .font(Theme.ui(11.5))
                    .foregroundStyle(Theme.mute)
                    .multilineTextAlignment(.center)
            } else {
                Text("No score yet this week").font(Theme.ui(14)).foregroundStyle(Theme.mute)
            }
            if let outlook = feed.score?.outlook {
                HStack(spacing: 6) {
                    Pill(text: "\(outlook.yours) lean yours", color: Theme.blue)
                    Pill(text: "\(outlook.coinFlip) coin flip\(outlook.coinFlip == 1 ? "" : "s")", color: Palette.lean("coin flip"))
                    Pill(text: "\(outlook.his) lean his", color: Theme.red)
                }
                Text("Where the 12 categories are heading by Sunday").font(Theme.ui(11)).foregroundStyle(Theme.mute)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 6)
    }
}

/// One line of the season: week, dates, opponent, score or "next".
struct SeasonRow: View {
    let week: SeasonWeek

    var body: some View {
        HStack(spacing: 12) {
            Text("W\(week.week)").font(Theme.display(15)).foregroundStyle(week.current ? .white : Theme.heading)
                .frame(width: 38, height: 26)
                .background(week.current ? Theme.blue : Theme.heading.opacity(0.1), in: RoundedRectangle(cornerRadius: 6))
            VStack(alignment: .leading, spacing: 1) {
                Text(week.opponent).font(Theme.ui(15, .semibold)).foregroundStyle(Theme.ink)
                Text("\(Dates.short(week.start)) – \(Dates.short(week.end))\(week.current ? " · this week" : "")").font(Theme.ui(11.5)).foregroundStyle(Theme.mute)
            }
            Spacer()
            if let text = week.scoreText {
                VStack(alignment: .trailing, spacing: 1) {
                    Text(text).font(Theme.display(18).monospacedDigit()).foregroundStyle(color)
                    Text(week.final == true ? "final" : "through \(week.through.map(Dates.short) ?? "")").font(Theme.ui(10.5)).foregroundStyle(Theme.mute)
                }
            } else {
                Text(week.current ? "no score yet" : "upcoming").font(Theme.ui(12)).foregroundStyle(Theme.mute)
            }
        }
    }

    private var color: Color {
        guard let won = week.won, let lost = week.lost else { return Theme.ink }
        return won > lost ? Theme.blue : won < lost ? Theme.red : Theme.ink
    }
}

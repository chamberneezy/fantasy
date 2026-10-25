import SwiftUI

/// Per-category: Yahoo's real score now, and where the week is heading, as a word.
struct MatchupView: View {
    @Environment(FeedStore.self) private var store

    var body: some View {
        NavigationStack {
            List {
                if let feed = store.feed {
                    if feed.leans.isEmpty {
                        BrandSection { Text("No opponent on file for week \(feed.week).").font(Theme.ui(15)).foregroundStyle(Theme.mute) }
                    } else {
                        BrandSection("Week \(feed.week) vs \(feed.opponent ?? "—")", footer: feed.leansNote) {
                            ScoreHeader(through: feed.yahooThrough)
                            ForEach(feed.leans) { LeanRow(lean: $0) }
                        }
                    }
                } else {
                    ProgressView()
                }
            }
            .brandScreen("Matchup")
            .refreshable { await store.refresh() }
        }
    }
}

struct ScoreHeader: View {
    let through: String?

    var body: some View {
        HStack {
            Text("CAT").frame(width: 48, alignment: .leading)
            Text(through.map { "YAHOO \(Dates.short($0).uppercased())  →  WEEK END" } ?? "WEEK END")
            Spacer()
            Text("LEAN")
        }
        .font(Theme.ui(10.5, .semibold))
        .foregroundStyle(Theme.mute)
    }
}

struct LeanRow: View {
    let lean: Lean

    var body: some View {
        HStack {
            Text(lean.cat).font(Theme.display(16)).foregroundStyle(Theme.heading).frame(width: 48, alignment: .leading)
            VStack(alignment: .leading, spacing: 1) {
                if let mine = lean.yahooMine, let theirs = lean.yahooTheirs {
                    Text("\(value(mine)) – \(value(theirs))")
                        .font(Theme.display(17).monospacedDigit())
                        .foregroundStyle(mine == theirs ? Theme.ink : (leads(mine, theirs) ? Theme.blue : Theme.red))
                }
                Text("→ \(value(lean.mine)) – \(value(lean.theirs))")
                    .font(Theme.ui(12).monospacedDigit())
                    .foregroundStyle(Theme.mute)
            }
            Spacer()
            Pill(text: lean.lean, color: Palette.lean(lean.lean))
        }
    }

    /// TO and PF: fewer is better.
    private func leads(_ mine: Double, _ theirs: Double) -> Bool {
        lean.cat == "TO" || lean.cat == "PF" ? mine < theirs : mine > theirs
    }

    private func value(_ number: Double) -> String {
        lean.cat.hasSuffix("%") ? String(format: "%.3f", number) : String(format: "%.0f", number)
    }
}

import SwiftUI

/// Per-category leans for the week. Words, not percentages.
struct MatchupView: View {
    @Environment(FeedStore.self) private var store

    var body: some View {
        NavigationStack {
            List {
                if let feed = store.feed {
                    if feed.leans.isEmpty {
                        Text("No opponent on file for week \(feed.week).").foregroundStyle(.secondary)
                    } else {
                        Section {
                            ForEach(feed.leans) { LeanRow(lean: $0) }
                        } header: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Week \(feed.week) vs \(feed.opponent ?? "—")")
                                if let through = feed.yahooThrough {
                                    Text("Yahoo now (through \(Dates.short(through)))  ·  week-end projection").font(.caption2)
                                } else {
                                    Text("Week-end projection").font(.caption2)
                                }
                            }
                        } footer: {
                            Text(feed.leansNote)
                        }
                    }
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Matchup")
            .refreshable { await store.refresh() }
        }
    }
}

struct LeanRow: View {
    let lean: Lean

    var body: some View {
        HStack {
            Text(lean.cat).font(.body.weight(.semibold)).frame(width: 48, alignment: .leading)
            VStack(alignment: .leading, spacing: 1) {
                if let mine = lean.yahooMine, let theirs = lean.yahooTheirs {
                    Text("\(value(mine)) – \(value(theirs))")
                        .font(.callout.monospacedDigit().weight(.semibold))
                        .foregroundStyle(leads(mine, theirs) ? .green : (mine == theirs ? .primary : .red))
                }
                Text("→ \(value(lean.mine)) – \(value(lean.theirs))")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Text(lean.lean)
                .font(.caption.bold())
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(color.opacity(0.18), in: Capsule())
                .foregroundStyle(color)
        }
    }

    private var color: Color {
        switch lean.lean {
        case "likely yours": return .green
        case "lean yours": return .mint
        case "coin flip": return .orange
        case "lean his": return .pink
        default: return .red
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

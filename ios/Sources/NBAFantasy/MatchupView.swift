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
                            Text("Week \(feed.week) vs \(feed.opponent ?? "—")")
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
            Text("\(value(lean.mine)) – \(value(lean.theirs))")
                .font(.callout.monospacedDigit())
                .foregroundStyle(.secondary)
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

    private func value(_ number: Double) -> String {
        lean.cat.hasSuffix("%") ? String(format: "%.3f", number) : String(format: "%.0f", number)
    }
}

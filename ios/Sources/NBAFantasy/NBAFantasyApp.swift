import SwiftUI

@main
struct NBAFantasyApp: App {
    @State private var store = FeedStore()
    @Environment(\.scenePhase) private var phase

    init() {
        Theme.registerFonts()
        Theme.styleBars()
    }

    var body: some Scene {
        WindowGroup {
            TabView {
                TodayView().tabItem { Label("Today", systemImage: "basketball") }
                MatchupView().tabItem { Label("Matchup", systemImage: "chart.bar") }
                NewsView().tabItem { Label("News", systemImage: "bell") }
                StatsView().tabItem { Label("Stats", systemImage: "list.number") }
            }
            .tint(Theme.blue)
            .environment(store)
            .task {
                await store.askForNotifications()
                await store.refresh()
            }
        }
        .onChange(of: phase) { _, now in
            if now == .active { Task { await store.refresh() } }
            if now == .background { FeedStore.scheduleBackgroundRefresh() }
        }
        .backgroundTask(.appRefresh(FeedStore.refreshTask)) {
            FeedStore.scheduleBackgroundRefresh()
            await store.refresh()
        }
    }
}

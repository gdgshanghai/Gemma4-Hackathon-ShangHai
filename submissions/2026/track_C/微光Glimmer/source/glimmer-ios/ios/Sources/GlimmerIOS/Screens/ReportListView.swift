import SwiftUI
import GlimmerCore

struct ReportListView: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var store: ReportConversationStore
    var onOpen: (ReportConversationRecord) -> Void = { _ in }
    var onSelectAnalyze: () -> Void = {}

    var body: some View {
        ZStack {
            GTheme.bg.ignoresSafeArea()

            VStack(spacing: 0) {
                header

                if store.records.isEmpty {
                    emptyState
                } else {
                    recordsList
                }

                Text(L10n.text(.localOnlyFootnote, language: languageStore.language))
                    .font(.system(size: 12, weight: .light))
                    .foregroundStyle(Color(hex: 0x666664))
                    .padding(.top, 4)

                GlimmerTabBar(active: .report) { tab in
                    if tab == .analyze { onSelectAnalyze() }
                }
            }
            .padding(.horizontal, 16)
        }
    }

    private var header: some View {
        HStack {
            Text(L10n.text(.reports, language: languageStore.language))
                .font(.system(size: 24, weight: .semibold))
                .foregroundStyle(GTheme.ink)
            Spacer()
            languageToggle
        }
        .padding(.top, 68)
        .padding(.bottom, 18)
    }

    private var languageToggle: some View {
        HStack(spacing: 0) {
            ForEach(GlimmerLanguage.allCases, id: \.self) { language in
                Button {
                    languageStore.setLanguage(language)
                } label: {
                    Text(L10n.languageToggleTitle(language))
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(languageStore.language == language ? GTheme.onInk : GTheme.ink)
                        .frame(width: 42, height: 30)
                        .background(
                            languageStore.language == language ? GTheme.ink : Color.clear,
                            in: Capsule()
                        )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(3)
        .background(GTheme.white.opacity(0.72), in: Capsule())
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Spacer()
            Text(L10n.text(.noReports, language: languageStore.language))
                .font(.system(size: 18, weight: .medium))
                .foregroundStyle(GTheme.ink)
            Text(L10n.text(.noReportsMessage, language: languageStore.language))
                .font(.system(size: 14, weight: .light))
                .foregroundStyle(GTheme.subtle)
                .multilineTextAlignment(.center)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    private var recordsList: some View {
        List {
            ForEach(store.records) { record in
                ReportRow(record: record)
                    .contentShape(RoundedRectangle(cornerRadius: 24))
                    .onTapGesture { onOpen(record) }
                    .listRowSeparator(.hidden)
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets(top: 6, leading: 0, bottom: 6, trailing: 0))
                    .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                        Button(role: .destructive) {
                            store.delete(record)
                        } label: {
                            Label(L10n.text(.delete, language: languageStore.language), systemImage: "trash")
                        }
                    }
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .background(Color.clear)
    }
}

private struct ReportRow: View {
    let record: ReportConversationRecord

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(record.timestamp)
                    .font(.system(size: 17, weight: .medium))
                    .foregroundStyle(GTheme.ink)
                    .lineLimit(1)
                    .minimumScaleFactor(0.85)

                Spacer(minLength: 8)

                Text(record.videoDuration)
                    .font(.system(size: 14, weight: .light))
                    .foregroundStyle(GTheme.subtle)
            }

            Text(record.conclusion)
                .font(.system(size: 15, weight: .light))
                .foregroundStyle(GTheme.inkSecondary)
                .lineSpacing(5)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 8) {
                Image(systemName: "play.fill")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(GTheme.onInk)
                    .frame(width: 24, height: 24)
                    .background(GTheme.ink, in: Circle())

                Text(record.videoTitle)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(GTheme.subtle)
                    .lineLimit(1)
                    .truncationMode(.middle)

                Spacer(minLength: 0)

                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(GTheme.faint)
            }
        }
        .padding(18)
        .background(GTheme.white.opacity(0.68), in: RoundedRectangle(cornerRadius: 24))
        .shadow(color: .black.opacity(0.035), radius: 8, x: 0, y: 3)
    }
}

#Preview {
    ReportListView(store: ReportConversationStore())
        .environment(AppLanguageStore())
}

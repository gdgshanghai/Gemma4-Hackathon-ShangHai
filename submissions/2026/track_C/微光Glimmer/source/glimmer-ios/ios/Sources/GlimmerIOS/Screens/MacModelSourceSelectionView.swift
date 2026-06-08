#if os(macOS)
import SwiftUI
import GlimmerCore

struct MacModelSourceSelectionView: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var message: String?
    var onDownload: () -> Void
    var onSelectLocalFiles: () -> Void

    var body: some View {
        ZStack(alignment: .topTrailing) {
            GTheme.bg.ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer(minLength: 0)

                bundleImage("glimmer_wordmark_clear")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 214)

                Text(L10n.text(.selectModelSource, language: languageStore.language))
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundStyle(GTheme.ink)
                    .multilineTextAlignment(.center)
                    .padding(.top, 42)

                VStack(spacing: 14) {
                    sourceButton(
                        title: L10n.text(.downloadModelSource, language: languageStore.language),
                        systemImage: "arrow.down.circle",
                        action: onDownload
                    )
                    sourceButton(
                        title: L10n.text(.loadLocalModelSource, language: languageStore.language),
                        systemImage: "folder",
                        action: onSelectLocalFiles
                    )
                }
                .padding(.top, 26)

                Text(message ?? L10n.text(.selectLocalModelHint, language: languageStore.language))
                    .font(.system(size: 13, weight: .regular))
                    .foregroundStyle(GTheme.subtle)
                    .multilineTextAlignment(.center)
                    .padding(.top, 18)
                    .fixedSize(horizontal: false, vertical: true)

                Spacer(minLength: 0)
            }
            .padding(.horizontal, 32)

            languageToggle
                .padding(.top, 16)
                .padding(.trailing, 20)
        }
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

    private func sourceButton(title: String, systemImage: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(title)
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(GTheme.ink)
                    .lineLimit(2)
                Spacer(minLength: 0)
                Image(systemName: systemImage)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(GTheme.onInk)
                    .frame(width: 36, height: 36)
                    .background(GTheme.ink, in: Circle())
            }
            .padding(.leading, 22)
            .padding(.trailing, 16)
            .frame(maxWidth: .infinity)
            .frame(height: 72)
            .background(GTheme.white)
            .clipShape(RoundedRectangle(cornerRadius: GTheme.cardRadius))
            .contentShape(RoundedRectangle(cornerRadius: GTheme.cardRadius))
        }
        .buttonStyle(.plain)
    }
}
#endif

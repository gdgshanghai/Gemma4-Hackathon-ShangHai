import SwiftUI
import GlimmerCore

struct ModelDownloadRegionSelectionView: View {
    @Environment(AppLanguageStore.self) private var languageStore

    var message: String?
    var onSelect: (ModelDownloadRegion) -> Void

    var body: some View {
        ZStack(alignment: .topTrailing) {
            GTheme.bg.ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer(minLength: 0)

                bundleImage("glimmer_wordmark_clear")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 214)

                Text(L10n.text(.selectModelDownloadRegion, language: languageStore.language))
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundStyle(GTheme.ink)
                    .multilineTextAlignment(.center)
                    .padding(.top, 42)

                VStack(spacing: 14) {
                    regionButton(.china)
                    regionButton(.global)
                }
                .padding(.top, 26)

                if let message {
                    Text(message)
                        .font(.system(size: 13, weight: .regular))
                        .foregroundStyle(GTheme.subtle)
                        .multilineTextAlignment(.center)
                        .padding(.top, 18)
                        .fixedSize(horizontal: false, vertical: true)
                }

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

    private func regionButton(_ region: ModelDownloadRegion) -> some View {
        Button {
            onSelect(region)
        } label: {
            HStack {
                Text(L10n.regionTitle(region, language: languageStore.language))
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(GTheme.ink)
                Spacer(minLength: 0)
                Image(systemName: "arrow.up")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(GTheme.onInk)
                    .rotationEffect(.degrees(90))
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

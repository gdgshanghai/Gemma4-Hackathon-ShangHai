import SwiftUI

public struct GlimmerRootView: View {
    @State private var languageStore = AppLanguageStore()

    public init() {}

    public var body: some View {
        AppRootView()
            .environment(languageStore)
            .task {
                await ParityTestRunner.runIfConfigured()
                await PreprocessParityRunner.runIfConfigured()
            }
    }
}

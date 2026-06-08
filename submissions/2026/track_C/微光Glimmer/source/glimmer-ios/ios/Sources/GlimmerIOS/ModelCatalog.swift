import CryptoKit
import Foundation

enum ModelCatalogError: LocalizedError {
    case missingManifest
    case invalidManifest
    case missingItem(String)
    case invalidLocalSelection
    case fileSizeMismatch(String)
    case checksumMismatch(String)

    var errorDescription: String? {
        switch self {
        case .missingManifest:
            return "ModelManifest.json is missing from the app bundle."
        case .invalidManifest:
            return "ModelManifest.json could not be decoded."
        case .missingItem(let id):
            return "Missing model manifest item: \(id)."
        case .invalidLocalSelection:
            return "Select both model-Q4_K_M.gguf and mmproj-bf16.gguf."
        case .fileSizeMismatch(let filename):
            return "Local model file size does not match manifest: \(filename)."
        case .checksumMismatch(let filename):
            return "Downloaded model checksum mismatch: \(filename)."
        }
    }
}

enum ModelCatalog {
    struct Manifest: Decodable {
        let version: Int
        let files: [Item]
    }

    struct Item: Decodable, Identifiable, Equatable {
        let id: String
        let filename: String
        let url: URL
        let chinaURL: URL?
        let byteSize: Int64
        let sha256: String

        var resource: String {
            URL(fileURLWithPath: filename).deletingPathExtension().lastPathComponent
        }
    }

    struct Receipt: Codable, Equatable {
        let filename: String
        let sourceURL: String
        let byteSize: Int64
        let sha256: String
    }

    static let manifest: Manifest = {
        guard let url = Bundle.main.url(forResource: "ModelManifest", withExtension: "json") else {
            assertionFailure(ModelCatalogError.missingManifest.localizedDescription)
            return Manifest(version: 0, files: [])
        }
        do {
            let data = try Data(contentsOf: url)
            return try JSONDecoder().decode(Manifest.self, from: data)
        } catch {
            assertionFailure("\(ModelCatalogError.invalidManifest.localizedDescription): \(error)")
            return Manifest(version: 0, files: [])
        }
    }()

    static var items: [Item] {
        manifest.files
    }

    static var directory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return base.appendingPathComponent("GlimmerModels", isDirectory: true)
    }

    static func item(id: String) -> Item? {
        items.first { $0.id == id }
    }

    static func item(resource: String) -> Item? {
        items.first { $0.resource == resource }
    }

    static func localURL(_ item: Item) -> URL {
        directory.appendingPathComponent(item.filename)
    }

    static func partialURL(_ item: Item) -> URL {
        directory.appendingPathComponent(item.filename + ".part")
    }

    static func downloadURLs(for item: Item, region: ModelDownloadRegion) -> [URL] {
        switch region {
        case .china:
            return uniqueURLs([item.chinaURL, item.url])
        case .global:
            return uniqueURLs([item.url, item.chinaURL])
        }
    }

    static func receiptURL(_ item: Item) -> URL {
        directory.appendingPathComponent(item.filename + ".receipt.json")
    }

    static func fileSize(_ url: URL) -> Int64 {
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
              let size = attrs[.size] as? NSNumber else {
            return 0
        }
        return size.int64Value
    }

    static func resolvedURL(resource: String) -> URL? {
        guard let item = item(resource: resource), hasTrustedLocalFile(item) else {
            return nil
        }
        return localURL(item)
    }

    /// 仅 macOS：若模型已随 app 打包进 bundle，直接用 bundle 内文件（跳过下载）。
    /// iOS 永远返回 nil —— 完全不影响 iOS 的首启动下载逻辑。
    static func bundledModelURL(_ item: Item) -> URL? {
#if os(macOS)
        return Bundle.main.url(forResource: item.resource, withExtension: "gguf")
#else
        return nil
#endif
    }

    static func resolvedModelFiles() throws -> AsdGgufModelFiles {
        guard let model = item(id: "model") else {
            throw ModelCatalogError.missingItem("model")
        }
        guard let mmproj = item(id: "mmproj") else {
            throw ModelCatalogError.missingItem("mmproj")
        }
        let modelURL: URL
        if hasTrustedLocalFile(model) {
            modelURL = localURL(model)
        } else if let bundled = bundledModelURL(model) {
            modelURL = bundled
        } else {
            throw AsdGgufRunnerError.missingModel
        }
        let mmprojURL: URL
        if hasTrustedLocalFile(mmproj) {
            mmprojURL = localURL(mmproj)
        } else if let bundled = bundledModelURL(mmproj) {
            mmprojURL = bundled
        } else {
            throw AsdGgufRunnerError.missingMmproj
        }
        return AsdGgufModelFiles(modelURL: modelURL, mmprojURL: mmprojURL)
    }

    static func allFilesTrusted() -> Bool {
        // 以 Application Support 里的文件为准（iOS 下载 / macOS 从 bundle 播种后都落在这）。
        // 这样“带模型首发版”首启动时为假 → 触发播种；播种后及“不带模型更新版”均为真。
        !items.isEmpty && items.allSatisfy { hasTrustedLocalFile($0) }
    }

#if os(macOS)
    /// 当前 app bundle 是否自带全部模型（“带模型首发版” = true；“不带模型更新版” = false）。
    static var hasBundledModels: Bool {
        !items.isEmpty && items.allSatisfy { bundledModelURL($0) != nil }
    }

    /// 把 bundle 内模型拷到 Application Support 并写 receipt（仅在尚未就绪时）。
    /// 播种一次后，后续“不带模型的更新版”可直接复用，无需重发 6GB、无需联网下载。
    static func seedBundledModelsIfNeeded(progress: ((Double) -> Void)? = nil) throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let total = max(items.reduce(Int64(0)) { $0 + $1.byteSize }, 1)
        var done: Int64 = 0
        for item in items {
            guard let src = bundledModelURL(item) else { continue }
            if hasTrustedLocalFile(item) {
                done += item.byteSize
                progress?(Double(done) / Double(total))
                continue
            }
            let dst = localURL(item)
            try? FileManager.default.removeItem(at: dst)
            try copyFileReportingProgress(from: src, to: dst, alreadyDone: done, total: total, progress: progress)
            done += item.byteSize
            try writeReceipt(for: item, sourceURL: item.url, byteSize: item.byteSize, sha256: item.sha256.lowercased())
            progress?(Double(done) / Double(total))
        }
    }

    static func localModelFiles(from urls: [URL]) throws -> AsdGgufModelFiles {
        guard let model = item(id: "model") else {
            throw ModelCatalogError.missingItem("model")
        }
        guard let mmproj = item(id: "mmproj") else {
            throw ModelCatalogError.missingItem("mmproj")
        }

        var selected: [String: URL] = [:]
        for url in urls {
            selected[url.lastPathComponent.lowercased()] = url
        }
        guard let modelURL = selected[model.filename.lowercased()],
              let mmprojURL = selected[mmproj.filename.lowercased()] else {
            throw ModelCatalogError.invalidLocalSelection
        }
        return AsdGgufModelFiles(modelURL: modelURL, mmprojURL: mmprojURL)
    }

    static func installLocalModelFiles(
        modelURL: URL,
        mmprojURL: URL,
        progress: ((Double) -> Void)? = nil
    ) throws {
        guard let model = item(id: "model") else {
            throw ModelCatalogError.missingItem("model")
        }
        guard let mmproj = item(id: "mmproj") else {
            throw ModelCatalogError.missingItem("mmproj")
        }

        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)

        let pairs: [(Item, URL)] = [(model, modelURL), (mmproj, mmprojURL)]
        let total = max(pairs.reduce(Int64(0)) { $0 + $1.0.byteSize }, 1)
        var done: Int64 = 0
        for (item, sourceURL) in pairs {
            try installLocalModelFile(
                item,
                sourceURL: sourceURL,
                alreadyDone: done,
                total: total,
                progress: progress
            )
            done += item.byteSize
            progress?(Double(done) / Double(total))
        }
    }

    private static func installLocalModelFile(
        _ item: Item,
        sourceURL: URL,
        alreadyDone: Int64,
        total: Int64,
        progress: ((Double) -> Void)?
    ) throws {
        let needsStop = sourceURL.startAccessingSecurityScopedResource()
        defer { if needsStop { sourceURL.stopAccessingSecurityScopedResource() } }

        guard fileSize(sourceURL) == item.byteSize else {
            throw ModelCatalogError.fileSizeMismatch(sourceURL.lastPathComponent)
        }

        let digest = try sha256Hex(of: sourceURL)
        guard digest == item.sha256.lowercased() else {
            throw ModelCatalogError.checksumMismatch(sourceURL.lastPathComponent)
        }

        let destination = localURL(item)
        let sameFile = sourceURL.standardizedFileURL.path == destination.standardizedFileURL.path
        if !sameFile {
            try? FileManager.default.removeItem(at: destination)
            do {
                try copyFileReportingProgress(
                    from: sourceURL,
                    to: destination,
                    alreadyDone: alreadyDone,
                    total: total,
                    progress: progress
                )
            } catch {
                try? FileManager.default.removeItem(at: destination)
                removeReceipt(item)
                throw error
            }
        }

        guard fileSize(destination) == item.byteSize else {
            removeReceipt(item)
            throw ModelCatalogError.fileSizeMismatch(item.filename)
        }

        try writeReceipt(for: item, sourceURL: sourceURL, byteSize: item.byteSize, sha256: digest)
    }

    private static func copyFileReportingProgress(
        from src: URL, to dst: URL, alreadyDone: Int64, total: Int64, progress: ((Double) -> Void)?
    ) throws {
        let input = try FileHandle(forReadingFrom: src)
        defer { try? input.close() }
        FileManager.default.createFile(atPath: dst.path, contents: nil)
        let output = try FileHandle(forWritingTo: dst)
        defer { try? output.close() }
        var copied: Int64 = 0
        while true {
            let data = try input.read(upToCount: 16 * 1024 * 1024) ?? Data()
            if data.isEmpty { break }
            try output.write(contentsOf: data)
            copied += Int64(data.count)
            progress?(Double(alreadyDone + copied) / Double(total))
        }
    }
#endif

    static func hasTrustedLocalFile(_ item: Item) -> Bool {
        let url = localURL(item)
        let size = fileSize(url)
        guard size > 0, let receipt = readReceipt(item) else {
            return false
        }
        return receipt.filename == item.filename
            && receipt.byteSize == size
            && receipt.sha256 == item.sha256.lowercased()
    }

    static func validateExistingFileIfNeeded(_ item: Item) async throws -> Bool {
        if hasTrustedLocalFile(item) {
            return true
        }

        let url = localURL(item)
        guard fileSize(url) == item.byteSize else {
            removeReceipt(item)
            return false
        }

        let digest = try sha256Hex(of: url)
        guard digest == item.sha256.lowercased() else {
            try? FileManager.default.removeItem(at: url)
            removeReceipt(item)
            return false
        }

        try writeReceipt(for: item, sourceURL: item.url, byteSize: item.byteSize, sha256: digest)
        return true
    }

    static func validPartialSize(_ item: Item) -> Int64 {
        let size = fileSize(partialURL(item))
        if size > item.byteSize {
            try? FileManager.default.removeItem(at: partialURL(item))
            return 0
        }
        return size
    }

    static func installValidatedPartial(_ item: Item, sourceURL: URL) throws {
        let partial = partialURL(item)
        guard fileSize(partial) == item.byteSize else {
            throw ModelDownloadError.incompleteFile(item.filename)
        }

        let digest = try sha256Hex(of: partial)
        guard digest == item.sha256.lowercased() else {
            try? FileManager.default.removeItem(at: partial)
            throw ModelCatalogError.checksumMismatch(item.filename)
        }

        let destination = localURL(item)
        try? FileManager.default.removeItem(at: destination)
        try FileManager.default.moveItem(at: partial, to: destination)
        try writeReceipt(for: item, sourceURL: sourceURL, byteSize: item.byteSize, sha256: digest)
    }

    static func removeLocalFile(_ item: Item) {
        try? FileManager.default.removeItem(at: localURL(item))
        removeReceipt(item)
    }

    static func removePartialFile(_ item: Item) {
        try? FileManager.default.removeItem(at: partialURL(item))
    }

    private static func uniqueURLs(_ urls: [URL?]) -> [URL] {
        var seen: Set<String> = []
        var result: [URL] = []
        for url in urls.compactMap({ $0 }) {
            let key = url.absoluteString
            guard seen.insert(key).inserted else {
                continue
            }
            result.append(url)
        }
        return result
    }

    private static func readReceipt(_ item: Item) -> Receipt? {
        let url = receiptURL(item)
        guard let data = try? Data(contentsOf: url) else {
            return nil
        }
        return try? JSONDecoder().decode(Receipt.self, from: data)
    }

    private static func writeReceipt(for item: Item, sourceURL: URL, byteSize: Int64, sha256: String) throws {
        let receipt = Receipt(
            filename: item.filename,
            sourceURL: sourceURL.absoluteString,
            byteSize: byteSize,
            sha256: sha256.lowercased()
        )
        let data = try JSONEncoder().encode(receipt)
        try data.write(to: receiptURL(item), options: [.atomic])
    }

    private static func removeReceipt(_ item: Item) {
        try? FileManager.default.removeItem(at: receiptURL(item))
    }

    private static func sha256Hex(of url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }

        var hasher = SHA256()
        while true {
            let data = try handle.read(upToCount: 1024 * 1024) ?? Data()
            if data.isEmpty {
                break
            }
            hasher.update(data: data)
        }

        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
}

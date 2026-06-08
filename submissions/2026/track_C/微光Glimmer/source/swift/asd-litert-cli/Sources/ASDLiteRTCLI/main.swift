import Foundation
import LiteRTLM

private let defaultModelRelativePath =
    "outputs/gemma4-asd-lora-r32-code9-zh-examples-noaudio-ep5-qlora-loftq-v1-litert-wi8-noaudio/asd-gemma4-code9-qlora-loftq-w8-noaudio.litertlm"

private let featureLabels: [(id: String, name: String)] = [
    ("B01", "缺少或回避眼神接触"),
    ("B02", "攻击性行为"),
    ("B03", "对感觉输入反应过强或过弱"),
    ("B04", "对语言互动无回应"),
    ("B05", "非典型语言"),
    ("B06", "排列物品"),
    ("B07", "自我击打或自伤行为"),
    ("B08", "自我旋转或旋转物体"),
    ("B09", "上肢刻板动作")
]

private let featureColumnNames = [
    "Absence or Avoidance of Eye Contact",
    "Aggressive Behavior",
    "Hyper- or Hyporeactivity to Sensory Input",
    "Non-Responsiveness to Verbal Interaction",
    "Non-Typical Language",
    "Object Lining-Up",
    "Self-Hitting or Self-Injurious Behavior",
    "Self-Spinning or Spinning Objects",
    "Upper Limb Stereotypies"
]

private struct CLIConfig {
    var videoPath: String?
    var evalCSVPath: String?
    var modelPath: String?
    var repoRoot: String?
    var cacheDir: String?
    var clipsDir: String?
    var outputJSONLPath: String?
    var explainREPL = false
    var historyMessageLimit = 10
    var chatMaxOutputTokens = 512
    var ffmpegPath = "ffmpeg"
    var ffprobePath = "ffprobe"
    var backend = "gpu"
    var visionBackend = "gpu"
}

private struct TimedResult<T> {
    let value: T
    let seconds: Double
}

private struct PreparedFrames {
    let directory: URL
    let paths: [String]
    let durationSeconds: Double
    let frameCount: Int
    let effectiveFPS: Double
}

private struct EvalSample {
    let index: Int
    let videoID: String
    let videoURL: URL
    let targetCode: String
    let targetVector: [Int]
}

private struct EvalRecord {
    let sample: EvalSample
    let predictedCode: String?
    let predictedVector: [Int]
    let rawResponse: String
    let parseOK: Bool
    let parseError: String?
    let durationSeconds: Double
    let frameCount: Int
    let effectiveFPS: Double
    let elapsedSeconds: Double
}

private struct Metrics {
    let parseRate: Double
    let microPrecision: Double
    let microRecall: Double
    let microF1: Double
    let macroPrecision: Double
    let macroRecall: Double
    let macroF1: Double
    let exactMatch: Double
    let perLabel: [LabelMetric]
}

private struct LabelMetric {
    let id: String
    let precision: Double
    let recall: Double
    let f1: Double
    let support: Int
    let truePositive: Int
    let falsePositive: Int
    let falseNegative: Int
}

private struct ChatTextMessage {
    let role: Role
    let text: String
}

private enum CLIError: Error, CustomStringConvertible {
    case usage(String)
    case missingFile(String)
    case missingRepoRoot
    case invalidBackend(String)
    case processFailed(command: String, status: Int32, output: String)
    case invalidDuration(String)
    case noFrames(URL)
    case invalidModelOutput(String)
    case invalidCSV(String)
    case invalidIntegerOption(option: String, value: String)

    var description: String {
        switch self {
        case .usage(let message):
            return message
        case .missingFile(let path):
            return "文件不存在：\(path)"
        case .missingRepoRoot:
            return "找不到 repo root。请在仓库内运行，或传入 --repo-root。"
        case .invalidBackend(let value):
            return "不支持的 backend：\(value)"
        case .processFailed(let command, let status, let output):
            return "命令执行失败，退出码 \(status)：\(command)\n\(output)"
        case .invalidDuration(let value):
            return "无法解析视频时长：\(value)"
        case .noFrames(let directory):
            return "ffmpeg 没有生成帧文件：\(directory.path)"
        case .invalidModelOutput(let raw):
            return "模型输出无法构成 9 位二进制码：\(raw)"
        case .invalidCSV(let message):
            return "CSV 格式错误：\(message)"
        case .invalidIntegerOption(let option, let value):
            return "参数 \(option) 必须是正整数，实际值：\(value)"
        }
    }
}

@main
struct ASDLiteRTCLI {
    static func main() async {
        let startedAt = Date()

        do {
            setLiteRTLMMinLogLevel(.error)

            let rawArgs = Array(CommandLine.arguments.dropFirst())
            if rawArgs.contains("-h") || rawArgs.contains("--help") {
                print(usageText())
                return
            }

            let config = try parseArguments(rawArgs)
            let repoRoot = try resolveRepoRoot(config.repoRoot)
            let modelURL = try resolveExistingFile(
                config.modelPath ?? defaultModelRelativePath,
                baseURL: repoRoot
            )
            let cacheURL = resolveCacheDir(config.cacheDir, repoRoot: repoRoot)

            if let evalCSVPath = config.evalCSVPath {
                let csvURL = try resolveExistingFile(evalCSVPath, baseURL: repoRoot)
                let clipsDir = resolvePath(
                    config.clipsDir ?? "data/raw/ASD-DS/clips_video",
                    baseURL: repoRoot
                )
                try await runBatchEval(
                    config: config,
                    repoRoot: repoRoot,
                    csvURL: csvURL,
                    clipsDir: clipsDir,
                    modelURL: modelURL,
                    cacheURL: cacheURL,
                    startedAt: startedAt
                )
                return
            }

            let videoURL = try resolveExistingFile(config.videoPath, baseURL: repoRoot)

            print("进度 1/6：检查输入完成")
            print("视频路径：\(videoURL.path)")
            print("模型路径：\(modelURL.path)")

            let promptBundle = try timed("进度 2/6：读取 prompt") {
                try loadPrompts(repoRoot: repoRoot)
            }

            let frames = try timed("进度 3/6：抽取视频帧") {
                try prepareFrames(
                    videoURL: videoURL,
                    ffmpegPath: config.ffmpegPath,
                    ffprobePath: config.ffprobePath
                )
            }
            defer {
                try? FileManager.default.removeItem(at: frames.value.directory)
            }
            print(
                String(
                    format: "抽帧完成：duration=%.3fs frames=%d fps=%.8f",
                    frames.value.durationSeconds,
                    frames.value.frameCount,
                    frames.value.effectiveFPS
                )
            )

            let engine = try await timedAsync("进度 4/6：加载 LiteRT-LM 模型") {
                let engineConfig = try EngineConfig(
                    modelPath: modelURL.path,
                    backend: try makeBackend(config.backend),
                    visionBackend: try makeBackend(config.visionBackend),
                    cacheDir: cacheURL.path
                )
                let engine = Engine(engineConfig: engineConfig)
                try await engine.initialize()
                return engine
            }
            print(String(format: "模型加载时间：%.3fs", engine.seconds))

            let responseText = try await timedAsync("进度 5/6：执行推理") {
                let samplerConfig = try SamplerConfig(
                    topK: 1,
                    topP: 1.0,
                    temperature: 0.0
                )
                let conversationConfig = ConversationConfig(
                    systemMessage: Message(promptBundle.value.system),
                    samplerConfig: samplerConfig,
                    maxOutputTokens: 9
                )
                let conversation = try await engine.value.createConversation(with: conversationConfig)
                var contents = frames.value.paths.map { Content.imageFile($0) }
                contents.append(Content.text(promptBundle.value.user))
                let response = try await conversation.sendMessage(Message(contents: contents))
                return response.toString
            }

            print("进度 6/6：解析输出")
            let code = try parseRawCode(responseText.value)
            print("raw output: \(code)")
            printExplanation(for: code)

            if config.explainREPL {
                try await runExplainREPL(
                    engine: engine.value,
                    systemPrompt: promptBundle.value.system,
                    userPrompt: promptBundle.value.user,
                    framePaths: frames.value.paths,
                    code: code,
                    historyMessageLimit: config.historyMessageLimit,
                    chatMaxOutputTokens: config.chatMaxOutputTokens
                )
            }

            let elapsed = Date().timeIntervalSince(startedAt)
            print(String(format: "总耗时：%.3fs", elapsed))
        } catch {
            fputs("错误：\(error)\n\n", stderr)
            fputs(usageText(), stderr)
            exit(1)
        }
    }
}

private func parseArguments(_ args: [String]) throws -> CLIConfig {
    var config = CLIConfig()
    var index = 0

    while index < args.count {
        let arg = args[index]
        switch arg {
        case "--eval-csv":
            config.evalCSVPath = try readOptionValue(args, &index, option: arg)
        case "--clips-dir":
            config.clipsDir = try readOptionValue(args, &index, option: arg)
        case "--output-jsonl":
            config.outputJSONLPath = try readOptionValue(args, &index, option: arg)
        case "--explain-repl":
            config.explainREPL = true
        case "--history-k":
            let value = try readOptionValue(args, &index, option: arg)
            guard let parsed = Int(value), parsed > 0 else {
                throw CLIError.invalidIntegerOption(option: arg, value: value)
            }
            config.historyMessageLimit = parsed
        case "--chat-max-output-tokens":
            let value = try readOptionValue(args, &index, option: arg)
            guard let parsed = Int(value), parsed > 0 else {
                throw CLIError.invalidIntegerOption(option: arg, value: value)
            }
            config.chatMaxOutputTokens = parsed
        case "--model-path":
            config.modelPath = try readOptionValue(args, &index, option: arg)
        case "--repo-root":
            config.repoRoot = try readOptionValue(args, &index, option: arg)
        case "--cache-dir":
            config.cacheDir = try readOptionValue(args, &index, option: arg)
        case "--ffmpeg":
            config.ffmpegPath = try readOptionValue(args, &index, option: arg)
        case "--ffprobe":
            config.ffprobePath = try readOptionValue(args, &index, option: arg)
        case "--backend":
            config.backend = try readOptionValue(args, &index, option: arg)
        case "--vision-backend":
            config.visionBackend = try readOptionValue(args, &index, option: arg)
        case "-h", "--help":
            throw CLIError.usage("显示帮助。")
        default:
            if arg.hasPrefix("-") {
                throw CLIError.usage("未知参数：\(arg)")
            }
            if config.videoPath != nil {
                throw CLIError.usage("只能传入一个视频路径。")
            }
            config.videoPath = arg
        }
        index += 1
    }

    if config.evalCSVPath != nil && config.videoPath != nil {
        throw CLIError.usage("--eval-csv 和单个视频路径不能同时使用。")
    }
    if config.evalCSVPath != nil && config.explainREPL {
        throw CLIError.usage("--explain-repl 只支持单个视频路径。")
    }
    if config.evalCSVPath == nil && config.videoPath == nil {
        throw CLIError.usage("缺少视频路径，或缺少 --eval-csv。")
    }
    return config
}

private func readOptionValue(_ args: [String], _ index: inout Int, option: String) throws -> String {
    let valueIndex = index + 1
    guard valueIndex < args.count else {
        throw CLIError.usage("参数 \(option) 缺少取值。")
    }
    index = valueIndex
    return args[valueIndex]
}

private func usageText() -> String {
    """

用法：
  swift run asd-litert-cli [options] <video-path>
  swift run asd-litert-cli [options] --eval-csv <csv-path>

选项：
  --eval-csv <path>         批量评估 CSV，读取 Video_ID 和 B01-B09 标签
  --clips-dir <path>        视频目录，默认 data/raw/ASD-DS/clips_video
  --output-jsonl <path>     批量评估预测输出，默认 outputs/litert_cli_eval/predictions.jsonl
  --explain-repl            单视频推理后进入解释对话 REPL，/quit 退出
  --history-k <n>           REPL 中保留最近 n 条文本消息，默认 10
  --chat-max-output-tokens <n> 解释/对话每轮最大输出 token，默认 512
  --model-path <path>       覆盖默认 .litertlm 模型路径
  --repo-root <path>        覆盖自动发现的仓库根目录
  --cache-dir <path>        覆盖 LiteRT-LM 编译缓存目录
  --ffmpeg <path>           ffmpeg 路径，默认从 PATH 查找
  --ffprobe <path>          ffprobe 路径，默认从 PATH 查找
  --backend <gpu|cpu>       主 backend，默认 gpu
  --vision-backend <gpu|cpu> 视觉 backend，默认 gpu

默认模型：
  \(defaultModelRelativePath)

"""
}

private func resolveRepoRoot(_ explicitPath: String?) throws -> URL {
    if let explicitPath {
        let url = URL(fileURLWithPath: expandTilde(explicitPath)).standardizedFileURL
        guard isRepoRoot(url) else {
            throw CLIError.missingRepoRoot
        }
        return url
    }

    var cursor = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).standardizedFileURL
    while true {
        if isRepoRoot(cursor) {
            return cursor
        }
        let parent = cursor.deletingLastPathComponent()
        if parent.path == cursor.path {
            throw CLIError.missingRepoRoot
        }
        cursor = parent
    }
}

private func isRepoRoot(_ url: URL) -> Bool {
    let systemPrompt = url.appendingPathComponent("prompts/zh/system.md").path
    let userPrompt = url.appendingPathComponent("prompts/zh/user.md").path
    return FileManager.default.fileExists(atPath: systemPrompt)
        && FileManager.default.fileExists(atPath: userPrompt)
}

private func resolveExistingFile(_ path: String?, baseURL: URL) throws -> URL {
    guard let path else {
        throw CLIError.usage("缺少文件路径。")
    }
    let url = resolvePath(path, baseURL: baseURL)
    guard FileManager.default.fileExists(atPath: url.path) else {
        throw CLIError.missingFile(url.path)
    }
    return url
}

private func resolvePath(_ path: String, baseURL: URL) -> URL {
    let expandedPath = expandTilde(path)
    if expandedPath.hasPrefix("/") {
        return URL(fileURLWithPath: expandedPath).standardizedFileURL
    }
    return baseURL.appendingPathComponent(expandedPath).standardizedFileURL
}

private func resolveCacheDir(_ path: String?, repoRoot: URL) -> URL {
    let url: URL
    if let path {
        let expandedPath = expandTilde(path)
        url = expandedPath.hasPrefix("/")
            ? URL(fileURLWithPath: expandedPath)
            : repoRoot.appendingPathComponent(expandedPath)
    } else {
        url = repoRoot.appendingPathComponent("outputs/litert_cli_cache")
    }
    try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    return url.standardizedFileURL
}

private func expandTilde(_ path: String) -> String {
    guard path == "~" || path.hasPrefix("~/") else {
        return path
    }
    let home = FileManager.default.homeDirectoryForCurrentUser.path
    if path == "~" {
        return home
    }
    return home + String(path.dropFirst())
}

private func loadPrompts(repoRoot: URL) throws -> (system: String, user: String) {
    let systemURL = repoRoot.appendingPathComponent("prompts/zh/system.md")
    let userURL = repoRoot.appendingPathComponent("prompts/zh/user.md")
    return (
        try String(contentsOf: systemURL, encoding: .utf8),
        try String(contentsOf: userURL, encoding: .utf8)
    )
}

private func runBatchEval(
    config: CLIConfig,
    repoRoot: URL,
    csvURL: URL,
    clipsDir: URL,
    modelURL: URL,
    cacheURL: URL,
    startedAt: Date
) async throws {
    print("批量评估：检查输入完成")
    print("CSV 路径：\(csvURL.path)")
    print("视频目录：\(clipsDir.path)")
    print("模型路径：\(modelURL.path)")

    let promptBundle = try timed("批量评估：读取 prompt") {
        try loadPrompts(repoRoot: repoRoot)
    }

    let samples = try timed("批量评估：读取 CSV") {
        try loadEvalSamples(csvURL: csvURL, clipsDir: clipsDir)
    }
    print("样本数：\(samples.value.count)")

    let engine = try await timedAsync("批量评估：加载 LiteRT-LM 模型") {
        let engineConfig = try EngineConfig(
            modelPath: modelURL.path,
            backend: try makeBackend(config.backend),
            visionBackend: try makeBackend(config.visionBackend),
            cacheDir: cacheURL.path
        )
        let engine = Engine(engineConfig: engineConfig)
        try await engine.initialize()
        return engine
    }
    print(String(format: "模型加载时间：%.3fs", engine.seconds))

    let outputURL = resolveBatchOutputURL(config.outputJSONLPath, repoRoot: repoRoot)
    try FileManager.default.createDirectory(
        at: outputURL.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    FileManager.default.createFile(atPath: outputURL.path, contents: nil)
    let outputHandle = try FileHandle(forWritingTo: outputURL)
    defer {
        try? outputHandle.close()
    }

    var records: [EvalRecord] = []
    records.reserveCapacity(samples.value.count)

    for sample in samples.value {
        let sampleStart = Date()
        let ordinal = sample.index + 1
        print("[\(ordinal)/\(samples.value.count)] \(sample.videoID) 开始")

        do {
            let frames = try prepareFrames(
                videoURL: sample.videoURL,
                ffmpegPath: config.ffmpegPath,
                ffprobePath: config.ffprobePath
            )
            defer {
                try? FileManager.default.removeItem(at: frames.directory)
            }

            let response = try await generateResponse(
                engine: engine.value,
                systemPrompt: promptBundle.value.system,
                userPrompt: promptBundle.value.user,
                framePaths: frames.paths
            )

            let parsed: (code: String?, vector: [Int], parseOK: Bool, parseError: String?)
            do {
                let code = try parseRawCode(response)
                parsed = (code, labelVector(from: code), true, nil)
            } catch {
                parsed = (nil, invalidFailureLabelVector(for: sample.targetVector), false, "\(error)")
            }

            let elapsed = Date().timeIntervalSince(sampleStart)
            let record = EvalRecord(
                sample: sample,
                predictedCode: parsed.code,
                predictedVector: parsed.vector,
                rawResponse: response,
                parseOK: parsed.parseOK,
                parseError: parsed.parseError,
                durationSeconds: frames.durationSeconds,
                frameCount: frames.frameCount,
                effectiveFPS: frames.effectiveFPS,
                elapsedSeconds: elapsed
            )
            records.append(record)
            try writeRecord(record, to: outputHandle)

            print(
                String(
                    format: "[%d/%d] %@ target=%@ pred=%@ parse=%@ elapsed=%.3fs",
                    ordinal,
                    samples.value.count,
                    sample.videoID,
                    sample.targetCode,
                    parsed.code ?? "<invalid>",
                    parsed.parseOK ? "ok" : "fail",
                    elapsed
                )
            )
        } catch {
            let elapsed = Date().timeIntervalSince(sampleStart)
            let record = EvalRecord(
                sample: sample,
                predictedCode: nil,
                predictedVector: invalidFailureLabelVector(for: sample.targetVector),
                rawResponse: "",
                parseOK: false,
                parseError: "\(error)",
                durationSeconds: 0,
                frameCount: 0,
                effectiveFPS: 0,
                elapsedSeconds: elapsed
            )
            records.append(record)
            try writeRecord(record, to: outputHandle)
            print(
                String(
                    format: "[%d/%d] %@ target=%@ pred=<failed> parse=fail elapsed=%.3fs",
                    ordinal,
                    samples.value.count,
                    sample.videoID,
                    sample.targetCode,
                    elapsed
                )
            )
        }
    }

    let metrics = computeMetrics(records)
    let metricsURL = outputURL.deletingPathExtension().appendingPathExtension("metrics.json")
    try writeMetrics(metrics, records: records, modelURL: modelURL, outputURL: metricsURL)

    print("")
    printMetricsTable(modelName: "swift test final", metrics: metrics)
    print("预测输出：\(outputURL.path)")
    print("指标输出：\(metricsURL.path)")
    print(String(format: "总耗时：%.3fs", Date().timeIntervalSince(startedAt)))
}

private func generateResponse(
    engine: Engine,
    systemPrompt: String,
    userPrompt: String,
    framePaths: [String]
) async throws -> String {
    let samplerConfig = try SamplerConfig(
        topK: 1,
        topP: 1.0,
        temperature: 0.0
    )
    let conversationConfig = ConversationConfig(
        systemMessage: Message(systemPrompt),
        samplerConfig: samplerConfig,
        maxOutputTokens: 9
    )
    let conversation = try await engine.createConversation(with: conversationConfig)
    var contents = framePaths.map { Content.imageFile($0) }
    contents.append(Content.text(userPrompt))
    let response = try await conversation.sendMessage(Message(contents: contents))
    return response.toString
}

private func runExplainREPL(
    engine: Engine,
    systemPrompt: String,
    userPrompt: String,
    framePaths: [String],
    code: String,
    historyMessageLimit: Int,
    chatMaxOutputTokens: Int
) async throws {
    let explainSystemPrompt = makeExplainSystemPrompt(from: systemPrompt)
    let explainUserPrompt = makeExplainUserPrompt(from: userPrompt)
    let assistantDiagnostic = assistantDiagnosticMessage(for: code)
    let videoObservationSummary = try await generateVideoObservationSummary(
        engine: engine,
        framePaths: framePaths
    )
    print("视频观察摘要：\(videoObservationSummary)")

    var history: [ChatTextMessage] = []
    var conversation = try await makeExplainConversation(
        engine: engine,
        systemPrompt: explainSystemPrompt,
        userPrompt: explainUserPrompt,
        assistantDiagnostic: assistantDiagnostic,
        videoObservationSummary: videoObservationSummary,
        history: history,
        historyMessageLimit: historyMessageLimit,
        maxOutputTokens: chatMaxOutputTokens
    )

    print("")
    print("解释对话：自动提问「为什么？」")
    let firstQuestion = "为什么？"
    let firstAnswer = try await sendExplainQuestion(
        conversation: conversation,
        question: firstQuestion,
        userPrompt: explainUserPrompt
    )
    print("assistant: \(firstAnswer)")
    history.append(ChatTextMessage(role: .user, text: firstQuestion))
    history.append(ChatTextMessage(role: .model, text: firstAnswer))

    print("")
    print("进入交互模式，输入 /quit 退出。")
    while true {
        print("> ", terminator: "")
        guard let line = readLine() else {
            print("")
            break
        }
        let question = line.trimmingCharacters(in: .whitespacesAndNewlines)
        if question == "/quit" {
            break
        }
        if question.isEmpty {
            continue
        }

        let answer = try await sendExplainQuestion(
            conversation: conversation,
            question: question,
            userPrompt: explainUserPrompt
        )
        print("assistant: \(answer)")
        history.append(ChatTextMessage(role: .user, text: question))
        history.append(ChatTextMessage(role: .model, text: answer))
        if history.count > historyMessageLimit {
            history = Array(history.suffix(historyMessageLimit))
            conversation = try await makeExplainConversation(
                engine: engine,
                systemPrompt: explainSystemPrompt,
                userPrompt: explainUserPrompt,
                assistantDiagnostic: assistantDiagnostic,
                videoObservationSummary: videoObservationSummary,
                history: history,
                historyMessageLimit: historyMessageLimit,
                maxOutputTokens: chatMaxOutputTokens
            )
        }
    }
}

private func makeExplainConversation(
    engine: Engine,
    systemPrompt: String,
    userPrompt: String,
    assistantDiagnostic: String,
    videoObservationSummary: String,
    history: [ChatTextMessage],
    historyMessageLimit: Int,
    maxOutputTokens: Int
) async throws -> Conversation {
    let samplerConfig = try SamplerConfig(
        topK: 1,
        topP: 1.0,
        temperature: 0.0
    )
    let retainedHistory = history.suffix(historyMessageLimit).map { message in
        Message(message.text, role: message.role)
    }
    let initialMessages = [
        Message(userPrompt, role: .user),
        Message(assistantDiagnostic, role: .model),
        Message(videoObservationContextMessage(videoObservationSummary), role: .user)
    ] + retainedHistory
    let conversationConfig = ConversationConfig(
        systemMessage: Message(systemPrompt),
        initialMessages: initialMessages,
        samplerConfig: samplerConfig,
        maxOutputTokens: maxOutputTokens
    )
    return try await engine.createConversation(with: conversationConfig)
}

private func generateVideoObservationSummary(
    engine: Engine,
    framePaths: [String]
) async throws -> String {
    let samplerConfig = try SamplerConfig(
        topK: 1,
        topP: 1.0,
        temperature: 0.0
    )
    let systemPrompt = """
你只负责为后续解释对话生成视频观察摘要。
请客观描述视频片段里能看到的场景、光照或阴影、人物位置和整体动作。
必须单独说明手臂或手部动作；如果看不清，也直接说看不清。
不要输出行为标签、二进制码、诊断判断或 Markdown；最多 3 句话。
"""
    let conversationConfig = ConversationConfig(
        systemMessage: Message(systemPrompt),
        samplerConfig: samplerConfig,
        maxOutputTokens: 128
    )
    let conversation = try await engine.createConversation(with: conversationConfig)
    var contents = framePaths.map { Content.imageFile($0) }
    contents.append(Content.text("请生成这个视频片段的观察摘要。"))
    let response = try await conversation.sendMessage(Message(contents: contents))
    return response.toString.trimmingCharacters(in: .whitespacesAndNewlines)
}

private func sendExplainQuestion(
    conversation: Conversation,
    question: String,
    userPrompt: String
) async throws -> String {
    let message = Message(makeExplainQuestionText(question, userPrompt: userPrompt))
    let response = try await conversation.sendMessage(message)
    return response.toString.trimmingCharacters(in: .whitespacesAndNewlines)
}

private func makeExplainSystemPrompt(from originalPrompt: String) -> String {
    """
你是一个面向家长的行为观察结果解释助手。你的回答应该像应用里的自然对话：简短、清楚、温和，直接回应用户的问题。

下面是原始分类任务的背景，只作为标签含义和任务边界参考：
\(makeExplanationPromptReference(from: originalPrompt))

现在已经进入视频问答和结果解释阶段。上一条 assistant message 里的 raw code 和中文解析是固定的解释对象；系统还会提供一段同一视频的观察摘要。
你可以回答任何与这个视频内容、观察摘要或筛查结果有关的问题，包括人物动作、场景、位置、光照、物体和已标记行为；回答时优先使用观察摘要里的具体画面信息。
如果用户问“为什么”，用自然语言说明这个标签可能对应的可观察动作；如果证据听起来较弱，可以用“可能”“不一定很明显”这类表达，但不要主动把结果推翻。
如果用户的问题和这个视频或结果无关，简短说明只能回答与这段视频有关的问题。
每次最多 3 句话，使用普通中文句子，不使用 Markdown、标题、编号或项目符号。不要输出医学诊断，也不要在每次回答里重复免责声明。
"""
}

private func makeExplainUserPrompt(from originalPrompt: String) -> String {
    """
原始分类提示的参考信息：
\(makeExplanationPromptReference(from: originalPrompt))

后续对话只回答和这段视频、观察摘要或已给出结果相关的问题。回答要像和用户交流，不像报告或免责声明；可以结合视频观察摘要里的具体画面。用户问“还有别的吗”时，直接说有没有其他标记，不主动逐项列出所有未标记类别，除非用户追问具体类别。
"""
}

private func makeExplanationPromptReference(from prompt: String) -> String {
    var edited = prompt
    if let exampleRange = edited.range(of: "\n示例：") {
        edited = String(edited[..<exampleRange.lowerBound])
    }

    let replacements = [
        "只返回 B01 到 B09 的 9 位二进制标签码。":
            "解释阶段不返回二进制标签码，只解释已经产生的标签结果。",
        "请只输出一行 9 位二进制标签码。":
            "解释阶段不再只输出二进制标签码。",
        "必须匹配这个格式：\n^[01]{9}$":
            "解释阶段不适用二进制格式约束。",
        "必须匹配这个格式：":
            "解释阶段不适用二进制格式约束。",
        "^[01]{9}$":
            "",
        "- 不要输出 B10。":
            "- B10 仍由应用端根据 B01 到 B09 派生。",
        "- 不要输出 JSON。":
            "- 解释阶段不输出 JSON。",
        "- 不要输出标签名、空格、标点、Markdown、置信度或解释。":
            "- 解释阶段可以输出标签名和简短解释，但不能使用 Markdown。",
        "- 完整回答必须正好是 9 个字符。":
            "- 解释阶段每次回答最多 3 句话。"
    ]

    for (source, replacement) in replacements {
        edited = edited.replacingOccurrences(of: source, with: replacement)
    }
    return edited.trimmingCharacters(in: .whitespacesAndNewlines)
}

private func makeExplainQuestionText(_ question: String, userPrompt: String) -> String {
    """
解释阶段上下文：
\(userPrompt)

当前用户问题：
\(question)

请直接回答这句话，语气自然一点；短问题就短答。如果问题涉及视频内容，就根据观察摘要里最接近的信息回答，不要因为摘要不完整就先拒绝；如果摘要确实没有相关信息，再说明看不出来。如果问题涉及筛查结果，就根据上一条 assistant 的 raw code 和中文解析回答。除非用户明确要求复核，否则不要把回答变成重新分类；如果问题和这段视频无关，就简短拒绝。最多 3 句话，不使用 Markdown，也不要重复免责声明。
"""
}

private func assistantDiagnosticMessage(for code: String) -> String {
    "上一条 assistant 诊断结果如下；这是后续解释对话的固定解释对象，不是新的分类请求。\n\n\(code)\n\n\(diagnosticExplanationText(for: code))"
}

private func videoObservationContextMessage(_ summary: String) -> String {
    """
同一视频片段的观察摘要如下。它只用于帮助解释上一条结果，不代表新的分类：
\(summary)
"""
}

private func loadEvalSamples(csvURL: URL, clipsDir: URL) throws -> [EvalSample] {
    let text = try String(contentsOf: csvURL, encoding: .utf8)
    let rows = parseCSV(text)
        .filter { row in row.contains { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty } }
    guard let header = rows.first else {
        throw CLIError.invalidCSV("empty file")
    }
    guard let videoIDColumn = header.firstIndex(of: "Video_ID") else {
        throw CLIError.invalidCSV("missing Video_ID column")
    }

    let labelColumns = try featureColumnNames.map { name -> Int in
        guard let index = header.firstIndex(of: name) else {
            throw CLIError.invalidCSV("missing label column: \(name)")
        }
        return index
    }

    var samples: [EvalSample] = []
    for row in rows.dropFirst() {
        guard videoIDColumn < row.count else {
            throw CLIError.invalidCSV("row \(samples.count + 2) missing Video_ID")
        }
        let videoID = row[videoIDColumn].trimmingCharacters(in: .whitespacesAndNewlines)
        if videoID.isEmpty {
            continue
        }
        let targetVector = try labelColumns.map { column -> Int in
            guard column < row.count else {
                throw CLIError.invalidCSV("row \(samples.count + 2) has too few columns")
            }
            let value = row[column].trimmingCharacters(in: .whitespacesAndNewlines)
            guard value == "0" || value == "1" else {
                throw CLIError.invalidCSV("row \(samples.count + 2) has non-binary label: \(value)")
            }
            return value == "1" ? 1 : 0
        }
        let videoURL = clipsDir.appendingPathComponent("\(videoID).mp4").standardizedFileURL
        guard FileManager.default.fileExists(atPath: videoURL.path) else {
            throw CLIError.missingFile(videoURL.path)
        }
        samples.append(
            EvalSample(
                index: samples.count,
                videoID: videoID,
                videoURL: videoURL,
                targetCode: targetVector.map(String.init).joined(),
                targetVector: targetVector
            )
        )
    }
    return samples
}

private func parseCSV(_ text: String) -> [[String]] {
    let text = text
        .replacingOccurrences(of: "\r\n", with: "\n")
        .replacingOccurrences(of: "\r", with: "\n")
    var rows: [[String]] = []
    var row: [String] = []
    var field = ""
    var inQuotes = false
    var index = text.startIndex

    while index < text.endIndex {
        let char = text[index]
        if char == "\"" {
            let next = text.index(after: index)
            if inQuotes && next < text.endIndex && text[next] == "\"" {
                field.append("\"")
                index = next
            } else {
                inQuotes.toggle()
            }
        } else if char == "," && !inQuotes {
            row.append(field)
            field = ""
        } else if (char == "\n" || char == "\r") && !inQuotes {
            row.append(field)
            field = ""
            rows.append(row.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) })
            row = []
            let next = text.index(after: index)
            if char == "\r" && next < text.endIndex && text[next] == "\n" {
                index = next
            }
        } else {
            field.append(char)
        }
        index = text.index(after: index)
    }

    if !field.isEmpty || !row.isEmpty {
        row.append(field)
        rows.append(row.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) })
    }
    if !rows.isEmpty {
        rows[0][0] = rows[0][0].replacingOccurrences(of: "\u{feff}", with: "")
    }
    return rows
}

private func resolveBatchOutputURL(_ path: String?, repoRoot: URL) -> URL {
    if let path {
        return resolvePath(path, baseURL: repoRoot)
    }
    return repoRoot.appendingPathComponent("outputs/litert_cli_eval/test_predictions.jsonl")
}

private func prepareFrames(
    videoURL: URL,
    ffmpegPath: String,
    ffprobePath: String
) throws -> PreparedFrames {
    let duration = try probeDuration(videoURL: videoURL, ffprobePath: ffprobePath)
    let frameCount = requestedFrameCount(durationSeconds: duration, fps: 1.0, maxFrames: 16)
    let effectiveFPS = sampledFrameFPS(frameCount: frameCount, durationSeconds: duration)
    let outputDir = FileManager.default.temporaryDirectory
        .appendingPathComponent("asd-litert-cli-\(UUID().uuidString)")
    try FileManager.default.createDirectory(at: outputDir, withIntermediateDirectories: true)

    let outputPattern = outputDir.appendingPathComponent("frame_%04d.jpg").path
    try runProcess(
        executable: ffmpegPath,
        arguments: [
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            videoURL.path,
            "-vf",
            String(format: "fps=%.8f,scale=512:-2", effectiveFPS),
            "-frames:v",
            "\(frameCount)",
            "-q:v",
            "2",
            outputPattern
        ]
    )

    let frameURLs = try FileManager.default.contentsOfDirectory(
        at: outputDir,
        includingPropertiesForKeys: nil
    )
    .filter { $0.pathExtension.lowercased() == "jpg" }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }

    guard !frameURLs.isEmpty else {
        throw CLIError.noFrames(outputDir)
    }

    return PreparedFrames(
        directory: outputDir,
        paths: frameURLs.map(\.path),
        durationSeconds: duration,
        frameCount: frameURLs.count,
        effectiveFPS: effectiveFPS
    )
}

private func probeDuration(videoURL: URL, ffprobePath: String) throws -> Double {
    let output = try runProcess(
        executable: ffprobePath,
        arguments: [
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            videoURL.path
        ]
    )
    let value = output.trimmingCharacters(in: .whitespacesAndNewlines)
    guard let duration = Double(value), duration.isFinite, duration >= 0 else {
        throw CLIError.invalidDuration(value)
    }
    return duration
}

private func requestedFrameCount(durationSeconds: Double, fps: Double, maxFrames: Int) -> Int {
    if durationSeconds <= 0 {
        return 1
    }
    return max(1, min(maxFrames, Int(ceil(durationSeconds * fps))))
}

private func sampledFrameFPS(frameCount: Int, durationSeconds: Double) -> Double {
    if durationSeconds <= 0 {
        return Double(frameCount)
    }
    return Double(frameCount) / durationSeconds
}

private func makeBackend(_ name: String) throws -> Backend {
    switch name {
    case "gpu":
        return .gpu
    case "cpu":
        return .cpu()
    default:
        throw CLIError.invalidBackend(name)
    }
}

private func parseRawCode(_ raw: String) throws -> String {
    let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
    guard trimmed.count >= 9 else {
        throw CLIError.invalidModelOutput(raw)
    }
    let prefix = String(trimmed.prefix(9))
    guard prefix.allSatisfy({ $0 == "0" || $0 == "1" }) else {
        throw CLIError.invalidModelOutput(raw)
    }
    return prefix
}

private func labelVector(from code: String) -> [Int] {
    code.map { $0 == "1" ? 1 : 0 }
}

private func invalidFailureLabelVector(for truth: [Int]) -> [Int] {
    truth.map { $0 == 1 ? 0 : 1 }
}

private func computeMetrics(_ records: [EvalRecord]) -> Metrics {
    var perLabel: [LabelMetric] = []
    var totalTP = 0
    var totalFP = 0
    var totalFN = 0

    for labelIndex in featureLabels.indices {
        var tp = 0
        var fp = 0
        var fn = 0
        var support = 0

        for record in records {
            let truth = record.sample.targetVector[labelIndex]
            let prediction = record.predictedVector[labelIndex]
            if truth == 1 {
                support += 1
            }
            if truth == 1 && prediction == 1 {
                tp += 1
            } else if truth == 0 && prediction == 1 {
                fp += 1
            } else if truth == 1 && prediction == 0 {
                fn += 1
            }
        }

        totalTP += tp
        totalFP += fp
        totalFN += fn

        perLabel.append(
            LabelMetric(
                id: featureLabels[labelIndex].id,
                precision: divide(Double(tp), Double(tp + fp)),
                recall: divide(Double(tp), Double(tp + fn)),
                f1: f1Score(tp: tp, fp: fp, fn: fn),
                support: support,
                truePositive: tp,
                falsePositive: fp,
                falseNegative: fn
            )
        )
    }

    let exactCount = records.filter { record in
        record.parseOK && record.sample.targetVector == record.predictedVector
    }.count
    let parseOKCount = records.filter(\.parseOK).count

    return Metrics(
        parseRate: divide(Double(parseOKCount), Double(records.count)),
        microPrecision: divide(Double(totalTP), Double(totalTP + totalFP)),
        microRecall: divide(Double(totalTP), Double(totalTP + totalFN)),
        microF1: f1Score(tp: totalTP, fp: totalFP, fn: totalFN),
        macroPrecision: average(perLabel.map(\.precision)),
        macroRecall: average(perLabel.map(\.recall)),
        macroF1: average(perLabel.map(\.f1)),
        exactMatch: divide(Double(exactCount), Double(records.count)),
        perLabel: perLabel
    )
}

private func divide(_ numerator: Double, _ denominator: Double) -> Double {
    guard denominator != 0 else {
        return 0
    }
    return numerator / denominator
}

private func f1Score(tp: Int, fp: Int, fn: Int) -> Double {
    let denominator = Double(2 * tp + fp + fn)
    guard denominator != 0 else {
        return 0
    }
    return Double(2 * tp) / denominator
}

private func average(_ values: [Double]) -> Double {
    guard !values.isEmpty else {
        return 0
    }
    return values.reduce(0, +) / Double(values.count)
}

private func writeRecord(_ record: EvalRecord, to handle: FileHandle) throws {
    let object: [String: Any] = [
        "index": record.sample.index,
        "video_id": record.sample.videoID,
        "video_path": record.sample.videoURL.path,
        "target_label_code": record.sample.targetCode,
        "predicted_label_code": record.predictedCode ?? NSNull(),
        "target_label_vector": record.sample.targetVector,
        "predicted_label_vector": record.predictedVector,
        "raw_prediction": record.rawResponse,
        "parse_ok": record.parseOK,
        "parse_error": record.parseError ?? NSNull(),
        "duration_seconds": record.durationSeconds,
        "frame_count": record.frameCount,
        "effective_fps": record.effectiveFPS,
        "elapsed_seconds": record.elapsedSeconds
    ]
    let data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
    handle.write(data)
    handle.write(Data("\n".utf8))
}

private func writeMetrics(
    _ metrics: Metrics,
    records: [EvalRecord],
    modelURL: URL,
    outputURL: URL
) throws {
    let object: [String: Any] = [
        "model": "swift test final",
        "model_path": modelURL.path,
        "sample_count": records.count,
        "parse_rate": metrics.parseRate,
        "micro": [
            "precision": metrics.microPrecision,
            "recall": metrics.microRecall,
            "f1": metrics.microF1
        ],
        "macro": [
            "precision": metrics.macroPrecision,
            "recall": metrics.macroRecall,
            "f1": metrics.macroF1
        ],
        "exact_match": metrics.exactMatch,
        "per_label": metrics.perLabel.map { label in
            [
                "id": label.id,
                "precision": label.precision,
                "recall": label.recall,
                "f1": label.f1,
                "support": label.support,
                "tp": label.truePositive,
                "fp": label.falsePositive,
                "fn": label.falseNegative
            ] as [String: Any]
        }
    ]
    let data = try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])
    try data.write(to: outputURL)
}

private func printMetricsTable(modelName: String, metrics: Metrics) {
    print("model                 parse   micro F1   macro F1   exact")
    print("-------------------   ------  --------   --------   ------")
    let paddedModelName = modelName.padding(toLength: 19, withPad: " ", startingAt: 0)
    print(
        String(
            format: "%@   %.4f  %.4f     %.4f     %.4f",
            paddedModelName,
            metrics.parseRate,
            metrics.microF1,
            metrics.macroF1,
            metrics.exactMatch
        )
    )
}

private func diagnosticExplanationText(for code: String) -> String {
    let chars = Array(code)
    var anyPositive = false
    var lines = ["解析结果："]

    for (index, label) in featureLabels.enumerated() {
        let observed = chars[index] == "1"
        anyPositive = anyPositive || observed
        lines.append("- \(label.id) \(label.name)：\(observed ? "观察到" : "未观察到")")
    }

    lines.append("- B10 背景类：\(!anyPositive ? "是" : "否")")
    lines.append("总体：\(anyPositive ? "观察到可见行为特征" : "未观察到 B01 到 B09 行为特征，归为背景类")")
    return lines.joined(separator: "\n")
}

private func printExplanation(for code: String) {
    print(diagnosticExplanationText(for: code))
}

@discardableResult
private func runProcess(executable: String, arguments: [String]) throws -> String {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    process.arguments = [executable] + arguments

    let pipe = Pipe()
    process.standardOutput = pipe
    process.standardError = pipe

    try process.run()
    process.waitUntilExit()

    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    let output = String(data: data, encoding: .utf8) ?? ""
    if process.terminationStatus != 0 {
        let command = ([executable] + arguments).joined(separator: " ")
        throw CLIError.processFailed(
            command: command,
            status: process.terminationStatus,
            output: output
        )
    }
    return output
}

private func timed<T>(_ label: String, operation: () throws -> T) throws -> TimedResult<T> {
    print("\(label) 开始")
    let start = Date()
    let value = try operation()
    let seconds = Date().timeIntervalSince(start)
    print(String(format: "\(label) 完成：%.3fs", seconds))
    return TimedResult(value: value, seconds: seconds)
}

private func timedAsync<T>(_ label: String, operation: () async throws -> T) async throws -> TimedResult<T> {
    print("\(label) 开始")
    let start = Date()
    let value = try await operation()
    let seconds = Date().timeIntervalSince(start)
    print(String(format: "\(label) 完成：%.3fs", seconds))
    return TimedResult(value: value, seconds: seconds)
}

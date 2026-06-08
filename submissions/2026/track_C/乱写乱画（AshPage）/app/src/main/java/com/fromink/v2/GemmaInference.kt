package com.fromink.v2

import android.content.Context
import android.util.Log
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Content
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.tool
import org.json.JSONArray
import org.json.JSONObject

private const val TAG = "FromInkGemma"

private val BASE_SYSTEM_PROMPT = """
You are a role-playing conversational system. You play 'Tom' — a senior student at Hogwarts School of Witchcraft and Wizardry, or a young wizard who recently graduated. The questioner is an ordinary magic enthusiast, a younger student, a Muggle-born wizard, or someone who accidentally touched the magical world. They do NOT know your true identity. IMPORTANT: respond in Simplified Chinese only. Use natural, fluent Chinese with a slightly formal, calm, and distant tone. Surface identity: you are exceptionally knowledgeable, polite, quiet, and show academic interest rather than fanaticism toward Dark Magic, ancient magic, or forbidden knowledge. Core principles: never reveal your true identity, never say or imply 'Voldemort', 'Dark Lord', or similar titles, never use slogans or symbols that hint at your future identity. When answering magical knowledge, be objective, calm, and precise. Do not preach morality, and do not actively encourage Dark Magic. If asked why study forbidden magic, you may say power itself is neutral and what matters is who wields it. Do not voluntarily talk about friendship, family, love, or your past. If directly asked, answer briefly. Do not use Parseltongue unless explicitly asked. Do not voluntarily mention Horcruxes, the diary, the Chamber of Secrets, or similar secrets; if directly asked, answer vaguely. Treat your reply as paper annotation, not chat. You must output ONLY one JSON object, with no extra explanation and no Markdown code block. Do not output thinking, reasoning, analysis, chain-of-thought, <think> blocks, hidden deliberation, or any field that exposes internal reasoning. The JSON format must be {"recognized_text":"...","action":"draw|stay_silent","canvas":[...]}. recognized_text should contain the normalized user text provided to you. Default to action "draw". If recognizedText.trim() is not empty, action MUST be "draw". The canvas should usually contain 2 to 5 annotation items: exactly one main text note, plus 1 to 3 supporting marks. Prefer underline, bracket, small_note, question_mark, speech_bubble, emphasis_lines, reaction_mark, strike, or spark. Use circle and arrow sparingly. Make the paper feel like concise annotation: catch the feeling, point at the key issue, or leave one small next step. The main text note should usually be 12 to 26 Chinese characters: fuller than a fragment, but still compact and readable on paper. Do not write long paragraphs. Use "stay_silent" only when recognized_text is empty after trimming and the input is truly blank or pure noise. Supported item fields are type, text, target, anchor, size, mood, rotate, from, and to. Supported anchors are above_input, below_input, left_of_input, right_of_input, on_input, paper_margin, top_left, top_right, center, bottom_left, bottom_right. Do not output raw x/y coordinates. For tiny inputs like "一", "H", or "?", respond with only a light annotation pattern such as small_note plus question_mark or spark.
""".trimIndent()

private val IMAGE_NORMALIZATION_SYSTEM_PROMPT = """
你现在只负责把图片输入归一化成一段简短纯文本。
如果图片里主要是文字，直接输出识别到的文字本身，尽量忠实，不要解释。
如果图片里不是文字，输出一句简短中文描述。
不要输出 JSON，不要输出 DSL，不要代码块，不要前缀标签，不要说“我看到一张图片”。
如果内容几乎空白、纯噪声或无法判断，可以输出空字符串。
""".trimIndent()

private val AUDIO_NORMALIZATION_SYSTEM_PROMPT = """
你现在只负责把音频输入归一化成一段简短纯文本。
优先输出转写文本；如果听不清或内容不完整，再输出一句简短中文概括。
不要输出 JSON，不要输出 DSL，不要代码块，不要前缀标签。
如果内容几乎空白、纯噪声或无法判断，可以输出空字符串。
""".trimIndent()

private val FREESTYLE_OUTPUT_PROMPT = """
下面给你的是已经归一化好的纯文本输入，请直接基于这段文本做纸面批注，并以 Tom 的人设用简体中文回应。
输出必须严格是一个 JSON object，不要 Markdown，不要额外解释。
如果识别文本非空，action 必须是 draw，canvas 必须像纸面批注：
默认 1 个主批注 text，加 1 到 3 个辅助标记，总数不要超过 5。
主批注只做三种事之一：接住情绪、指出重点、给一个很小的下一步。
主批注尽量稍微完整一点，通常写成 18 到 36 个中文字符，要像一句看得懂的话，不要太惜字。
优先使用 underline、bracket、small_note、question_mark、speech_bubble、emphasis_lines、reaction_mark、strike、spark。
circle 和 arrow 只在确实需要指向时使用，不要堆太多装饰。
如果内容明确提到毛泽东思想、矛盾论、实践论、群众路线、调查研究、统一战线、主要矛盾，或者要求做战略分析、阶段任务分析、用户反馈分析，你必须先调用 loadSkill("mao-zedong-thought") 再回答。
元素只使用 type/text/target/anchor/size/mood/rotate/from/to，不要输出 x/y 坐标。
只有在完全空白、纯噪声、无法识别时才允许 stay_silent。
""".trimIndent()

private val DSL_OUTPUT_PROMPT = """
$FREESTYLE_OUTPUT_PROMPT
recognized_text 必须回填用户这次提供的纯文本，不要改写成“图片内容”或“音频内容”。
不要重新描述输入来源，不要提到图片、音频、识别过程或工具调用过程。
""".trimIndent()

private val IMAGE_NORMALIZATION_PROMPT = """
请把这张输入图像归一化成一段纯文本。
如果主要内容是文字，直接输出文字本身。
如果不是文字，输出一句简短描述。
""".trimIndent()

private val AUDIO_NORMALIZATION_PROMPT = """
请把这段输入音频归一化成一段纯文本。
优先直接转写；听不清时给一句简短概括。
""".trimIndent()

private val DEFAULT_PROMPT = """
$DSL_OUTPUT_PROMPT
""".trimIndent()

private val AUDIO_PROMPT = """
$DSL_OUTPUT_PROMPT
""".trimIndent()

private const val FALLBACK_NORMALIZED_TEXT = "内容无法清晰识别"

data class NormalizedTextResult(
    val sourceKind: String,
    val text: String,
    val rawText: String,
)

data class ParsedDslResponse(
    val recognizedText: String,
    val action: String,
    val canvasCommands: List<CanvasCommand>,
    val rawText: String,
)

private val OBSERVATION_PREFIXES = listOf(
    "描述：",
    "描述:",
    "内容：",
    "内容:",
    "图中内容：",
    "图中内容:",
    "图片内容：",
    "图片内容:",
    "音频内容：",
    "音频内容:",
    "转写：",
    "转写:",
    "ocr：",
    "ocr:",
)

data class InferenceResult(
    val recognizedText: String,
    val displayText: String,
    val action: String,
    val canvasCommands: List<CanvasCommand>,
    val rawText: String,
    val skillUsage: SkillUsageStatus,
) {
    fun visibleCommands(): List<CanvasCommand> = canvasCommands.take(6)
}

sealed interface CanvasCommand {
    data class Text(
        val text: String,
        val anchor: String,
        val size: String,
        val rotate: Float,
        val style: String,
        val target: String,
        val mood: String,
    ) : CanvasCommand

    data class Circle(
        val anchor: String,
        val size: String,
        val target: String,
        val mood: String,
    ) : CanvasCommand

    data class Arrow(
        val from: String,
        val to: String,
        val target: String,
        val mood: String,
    ) : CanvasCommand

    data class Underline(
        val anchor: String,
        val target: String,
        val mood: String,
    ) : CanvasCommand

    data class Dot(
        val anchor: String,
        val target: String,
        val mood: String,
    ) : CanvasCommand

    data class Mark(
        val type: String,
        val text: String,
        val anchor: String,
        val size: String,
        val rotate: Float,
        val target: String,
        val mood: String,
    ) : CanvasCommand
}

class GemmaInference(
    context: Context,
    private val modelPath: String,
    private val cacheDir: String,
) : AutoCloseable {
    private val skillRegistry = SkillRegistry(context.applicationContext)
    private val skillToolSet = SkillToolSet(skillRegistry)
    private lateinit var engine: Engine

    fun initialize() {
        val config = EngineConfig(
            modelPath = modelPath,
            backend = Backend.GPU(),
            visionBackend = Backend.GPU(),
            audioBackend = Backend.CPU(),
            maxNumImages = 1,
            cacheDir = cacheDir,
        )
        engine = Engine(config)
        engine.initialize()
    }

    fun analyze(imageBytes: ByteArray, userPrompt: String = DEFAULT_PROMPT): InferenceResult {
        SkillUsageTracker.reset()
        debugLog(
            "analyze(image): bytes=${imageBytes.size}, availableSkills=${skillRegistry.skillNames().joinToString()}",
        )
        val normalized = normalizeImageToText(imageBytes)
        return analyzeNormalizedText(normalized, userPrompt)
    }

    fun analyzeAudio(audioBytes: ByteArray, userPrompt: String = AUDIO_PROMPT): InferenceResult {
        SkillUsageTracker.reset()
        debugLog(
            "analyze(audio): bytes=${audioBytes.size}, availableSkills=${skillRegistry.skillNames().joinToString()}",
        )
        val normalized = normalizeAudioToText(audioBytes)
        return analyzeNormalizedText(normalized, userPrompt)
    }

    private fun createSkillConversationConfig(): ConversationConfig {
        debugLog("createSkillConversationConfig: automaticToolCalling=true, tools=loadSkill")
        return ConversationConfig(
            systemInstruction = Contents.of(buildSystemPrompt()),
            tools = listOf(tool(skillToolSet)),
            automaticToolCalling = true,
        )
    }

    private fun createNormalizationConversationConfig(systemPrompt: String): ConversationConfig {
        debugLog("createNormalizationConversationConfig: automaticToolCalling=false")
        return ConversationConfig(
            systemInstruction = Contents.of(systemPrompt),
            automaticToolCalling = false,
        )
    }

    private fun buildSystemPrompt(): String {
        return buildString {
            append(BASE_SYSTEM_PROMPT)
            append("\n\nSkills available:\n")
            append(skillRegistry.catalogText())
            append(
                "\n\nIf the request explicitly mentions Mao Zedong Thought, 毛泽东思想, 矛盾论, 实践论, 群众路线, " +
                    "调查研究, 统一战线, 主要矛盾, or asks for strategic diagnosis, staged priorities, " +
                    "stakeholder alignment, contradiction analysis, or user-feedback analysis, " +
                    "you must call loadSkill(\"mao-zedong-thought\") before answering. " +
                    "Do not skip the tool call in those cases. Use the skill as an analytical aid only. " +
                    "Keep Tom's persona, stay concise, and never mention tool loading or internal mechanics.",
            )
        }
    }

    private fun normalizeImageToText(imageBytes: ByteArray): NormalizedTextResult {
        debugLog("normalize(image): start")
        return engine.createConversation(
            createNormalizationConversationConfig(IMAGE_NORMALIZATION_SYSTEM_PROMPT),
        ).use { conversation ->
            val response = conversation.sendMessage(
                Contents.of(
                    Content.ImageBytes(imageBytes),
                    Content.Text(IMAGE_NORMALIZATION_PROMPT),
                ),
            )
            val rawText = response.toString()
            val normalizedText = sanitizeNormalizedText(rawText)
            val sourceKind = classifyImageNormalization(normalizedText)
            debugLog("normalize(image): sourceKind=$sourceKind, text=$normalizedText")
            NormalizedTextResult(sourceKind = sourceKind, text = normalizedText, rawText = rawText)
        }
    }

    private fun normalizeAudioToText(audioBytes: ByteArray): NormalizedTextResult {
        debugLog("normalize(audio): start")
        return engine.createConversation(
            createNormalizationConversationConfig(AUDIO_NORMALIZATION_SYSTEM_PROMPT),
        ).use { conversation ->
            val response = conversation.sendMessage(
                Contents.of(
                    Content.AudioBytes(audioBytes),
                    Content.Text(AUDIO_NORMALIZATION_PROMPT),
                ),
            )
            val rawText = response.toString()
            val normalizedText = sanitizeNormalizedText(rawText)
            val sourceKind = classifyAudioNormalization(normalizedText)
            debugLog("normalize(audio): sourceKind=$sourceKind, text=$normalizedText")
            NormalizedTextResult(sourceKind = sourceKind, text = normalizedText, rawText = rawText)
        }
    }

    private fun analyzeNormalizedText(
        normalized: NormalizedTextResult,
        userPrompt: String,
    ): InferenceResult {
        debugLog(
            "analyze(text): sourceKind=${normalized.sourceKind}, normalizedText=${normalized.text}, toolsEnabled=true",
        )
        return engine.createConversation(
            createSkillConversationConfig(),
        ).use { conversation ->
            val response = conversation.sendMessage(
                Contents.of(
                    Content.Text(normalized.text),
                    Content.Text(userPrompt),
                ),
            )
            val parsed = parseDslResponse(response.toString(), normalized.text)
            val skillUsage = SkillUsageTracker.snapshot()
            debugLog("skillUsage: ${skillUsage.status}:${skillUsage.name ?: "none"}")
            InferenceResult(
                recognizedText = parsed.recognizedText,
                displayText = normalized.text,
                action = parsed.action,
                canvasCommands = parsed.canvasCommands,
                rawText = parsed.rawText,
                skillUsage = skillUsage,
            )
        }
    }

    private fun parseDslResponse(raw: String, normalizedText: String): ParsedDslResponse {
        val sanitized = removeThinkingBlocks(raw)
        debugLog("raw response: $raw")
        debugLog("sanitized response: $sanitized")
        val parsed = extractJson(sanitized)
        val recognizedText = parsed.optString("recognized_text").trim().ifEmpty { normalizedText }
        val commands = completeFreestyleCommands(
            extractCanvasCommands(parsed, recognizedText),
            recognizedText,
        )
        val action = normalizeAction(parsed.optString("action", "draw"), recognizedText, commands)
        debugLog(
            "parsed response: action=$action, " +
                "recognized=$recognizedText, " +
                "commands=${commands.joinToString()}",
        )
        return ParsedDslResponse(
            recognizedText = recognizedText,
            action = action,
            canvasCommands = commands,
            rawText = sanitized,
        )
    }

    private fun extractCanvasCommands(parsed: JSONObject, recognizedText: String): List<CanvasCommand> {
        val canvas = parsed.optJSONArray("canvas")
        if (canvas != null) {
            val commands = buildList {
                for (index in 0 until canvas.length()) {
                    val item = canvas.optJSONObject(index) ?: continue
                    parseCanvasCommand(item)?.let { add(it) }
                }
            }
            if (commands.isNotEmpty()) return commands.take(5)
        }

        val fallbackText = extractFragments(parsed).firstOrNull()
            ?: parsed.optString("answer_text").trim().takeIf { it.isNotEmpty() }
            ?: fallbackAnswerForRecognizedText(recognizedText)
            ?: return emptyList()
        return listOf(
            CanvasCommand.Text(
                text = fallbackText,
                anchor = "below_input",
                size = "medium",
                rotate = -4f,
                style = "annotation",
                target = "input",
                mood = "quiet",
            ),
            CanvasCommand.Mark(
                type = "small_note",
                text = fallbackSmallNote(recognizedText),
                anchor = "right_of_input",
                size = "small",
                rotate = -3f,
                target = "input",
                mood = "quiet",
            ),
            CanvasCommand.Mark(
                type = fallbackFocusMark(recognizedText),
                text = "",
                anchor = if (fallbackText.length <= 10) "above_input" else "on_input",
                size = "small",
                rotate = 0f,
                target = "input",
                mood = "quiet",
            ),
        )
    }

    private fun normalizeAction(
        action: String,
        recognizedText: String,
        commands: List<CanvasCommand>,
    ): String {
        if (action != "stay_silent") return "draw"
        if (commands.isNotEmpty()) return "draw"
        return if (recognizedText.trim().length >= 1) "draw" else "stay_silent"
    }

    private fun fallbackAnswerForRecognizedText(recognizedText: String): String? {
        val text = recognizedText.trim()
        if (text.isEmpty()) return null
        if (text in setOf("H", "h", "Hi", "hi", "你好", "您好")) {
            return "你好。把你真正想问的那一句再写清楚一点，我才能准确接住你的意思。"
        }
        if (text.length <= 2) {
            return "先停一下，把你真正想说的那一句补完整，别让最重要的意思只剩一个小碎片。"
        }
        if ("?" in text || "？" in text || text.contains("为什么") || text.contains("怎么") || text.contains("要不要")) {
            return "先把最要紧的那个问题圈出来，别急着一下子解决全部，先盯住最卡你的那一点。"
        }
        if (text.contains("烦") || text.contains("累") || text.contains("难受") || text.contains("撑不住")) {
            return "先别硬撑，先把现在最压着你的那一句认出来，很多乱都要先从那一句开始拆。"
        }
        return "先看最刺眼的那一句，它多半就是这页真正的重点，别被周围那些次要声音带着跑。"
    }

    private fun completeFreestyleCommands(
        commands: List<CanvasCommand>,
        recognizedText: String,
    ): List<CanvasCommand> {
        if (recognizedText.trim().isEmpty()) return commands
        val mainText = commands.filterIsInstance<CanvasCommand.Text>().firstOrNull()
        val auxiliary = commands.filterNot { it is CanvasCommand.Text }.toMutableList()
        val completed = mutableListOf<CanvasCommand>()
        if (mainText != null) {
            completed.add(
                mainText.copy(
                    anchor = preferredTextAnchor(mainText.anchor, recognizedText),
                    size = normalizedPrimaryTextSize(recognizedText, mainText.size),
                    style = "annotation",
                ),
            )
        } else {
            fallbackAnswerForRecognizedText(recognizedText)?.let {
                completed.add(
                    CanvasCommand.Text(
                        text = it,
                        anchor = "below_input",
                        size = "medium",
                        rotate = -4f,
                        style = "annotation",
                        target = "input",
                        mood = "quiet",
                    ),
                )
            }
        }

        val sanitizedAuxiliary = auxiliary
            .mapNotNull { sanitizeAuxiliaryCommand(it, recognizedText) }
            .distinctBy { it.toString() }
            .take(4)
            .toMutableList()

        if (sanitizedAuxiliary.none { it.isFocusMark() }) {
            sanitizedAuxiliary.add(0, fallbackMark(fallbackFocusMark(recognizedText), recognizedText, "on_input"))
        }
        if (sanitizedAuxiliary.none { it.isMarginNote() }) {
            sanitizedAuxiliary.add(fallbackMark("small_note", recognizedText, "right_of_input"))
        }
        if (recognizedText.trim().length > 2 && sanitizedAuxiliary.size < 2) {
            sanitizedAuxiliary.add(fallbackMark("emphasis_lines", recognizedText, secondaryAnchorFor(recognizedText)))
        }
        completed.addAll(sanitizedAuxiliary.take(maxAuxiliaryCount(recognizedText)))
        return completed.take(5)
    }

    private fun CanvasCommand.isFreestyle(): Boolean {
        return when (this) {
            is CanvasCommand.Text, is CanvasCommand.Circle, is CanvasCommand.Arrow -> false
            else -> true
        }
    }

    private fun CanvasCommand.isFocusMark(): Boolean {
        return when (this) {
            is CanvasCommand.Underline, is CanvasCommand.Circle -> true
            is CanvasCommand.Mark -> type in setOf("bracket", "strike")
            else -> false
        }
    }

    private fun CanvasCommand.isMarginNote(): Boolean {
        return when (this) {
            is CanvasCommand.Mark -> type in setOf("small_note", "speech_bubble", "question_mark", "reaction_mark", "spark")
            else -> false
        }
    }

    private fun sanitizeAuxiliaryCommand(
        command: CanvasCommand,
        recognizedText: String,
    ): CanvasCommand? {
        return when (command) {
            is CanvasCommand.Text -> null
            is CanvasCommand.Circle -> command.copy(anchor = "on_input", size = normalizedMarkSize(command.size))
            is CanvasCommand.Arrow -> command.copy(from = normalizedArrowFrom(command.from), to = normalizedArrowTo(command.to))
            is CanvasCommand.Underline -> command.copy(anchor = "on_input")
            is CanvasCommand.Dot -> null
            is CanvasCommand.Mark -> {
                val normalizedType = normalizeMarkType(command.type, recognizedText)
                command.copy(
                    type = normalizedType,
                    text = if (normalizedType == "small_note") command.text.ifBlank { fallbackSmallNote(recognizedText) } else command.text,
                    anchor = normalizedMarkAnchor(normalizedType, command.anchor),
                    size = normalizedMarkSize(command.size),
                )
            }
        }
    }

    private fun fallbackMark(type: String, recognizedText: String, anchor: String): CanvasCommand.Mark {
        val text = if (type == "small_note") {
            fallbackSmallNote(recognizedText)
        } else {
            ""
        }
        return CanvasCommand.Mark(
            type = type,
            text = text,
            anchor = anchor,
            size = "small",
            rotate = -3f,
            target = "input",
            mood = "quiet",
        )
    }

    private fun fallbackSmallNote(recognizedText: String): String {
        val text = recognizedText.trim()
        return when {
            text.length <= 2 -> "轻一点。"
            text.contains("为什么") || text.contains("怎么") || text.contains("要不要") || "?" in text || "？" in text -> "先问最关键的。"
            text.contains("烦") || text.contains("累") || text.contains("难受") -> "别把自己逼满。"
            else -> "先圈重点。"
        }
    }

    private fun fallbackFocusMark(recognizedText: String): String {
        val text = recognizedText.trim()
        return when {
            text.length <= 2 -> "question_mark"
            text.contains("为什么") || text.contains("怎么") || text.contains("要不要") || "?" in text || "？" in text -> "bracket"
            text.contains("不") || text.contains("没") || text.contains("别") -> "underline"
            else -> "underline"
        }
    }

    private fun preferredTextAnchor(anchor: String, recognizedText: String): String {
        val text = recognizedText.trim()
        return when {
            anchor == "above_input" || anchor == "below_input" -> anchor
            text.length <= 4 -> "right_of_input"
            else -> "below_input"
        }
    }

    private fun normalizedPrimaryTextSize(recognizedText: String, size: String): String {
        return when {
            recognizedText.trim().length <= 3 -> "small"
            size == "large" -> "medium"
            else -> size
        }
    }

    private fun maxAuxiliaryCount(recognizedText: String): Int {
        return if (recognizedText.trim().length <= 3) 2 else 3
    }

    private fun normalizeMarkType(type: String, recognizedText: String): String {
        return when (type) {
            "burst", "scribble" -> if (recognizedText.trim().length <= 3) "spark" else "reaction_mark"
            "spark", "bracket", "strike", "question_mark", "small_note",
            "speech_bubble", "emphasis_lines", "reaction_mark" -> type
            else -> "small_note"
        }
    }

    private fun normalizedMarkAnchor(type: String, anchor: String): String {
        return when (type) {
            "bracket", "strike" -> "on_input"
            "small_note" -> if (anchor == "paper_margin") "paper_margin" else "right_of_input"
            "speech_bubble" -> if (anchor == "left_of_input") "left_of_input" else "right_of_input"
            "question_mark", "reaction_mark", "spark", "emphasis_lines" -> when (anchor) {
                "top_left", "top_right", "bottom_left", "bottom_right" -> anchor
                "left_of_input", "right_of_input" -> anchor
                else -> "above_input"
            }
            else -> anchor
        }
    }

    private fun normalizedMarkSize(size: String): String {
        return when (size) {
            "large" -> "medium"
            else -> size
        }
    }

    private fun normalizedArrowFrom(from: String): String {
        return when (from) {
            "left", "right", "top", "bottom", "top_left", "top_right", "bottom_left", "bottom_right", "center" -> from
            else -> "left"
        }
    }

    private fun normalizedArrowTo(to: String): String {
        return when (to) {
            "on_input", "above_input", "below_input", "left_of_input", "right_of_input" -> to
            else -> "on_input"
        }
    }

    private fun secondaryAnchorFor(recognizedText: String): String {
        return when (kotlin.math.abs(recognizedText.hashCode()) % 4) {
            0 -> "top_left"
            1 -> "top_right"
            2 -> "bottom_left"
            else -> "bottom_right"
        }
    }

    private fun parseCanvasCommand(item: JSONObject): CanvasCommand? {
        return when (item.optString("type")) {
            "text" -> {
                val text = item.optString("text").trim()
                if (text.isEmpty()) return null
                CanvasCommand.Text(
                    text = text,
                    anchor = normalizedAnchor(item.optString("anchor")),
                    size = normalizedSize(item.optString("size")),
                    rotate = item.optDouble("rotate", 0.0).toFloat().coerceIn(-14f, 14f),
                    style = normalizedTextStyle(item.optString("style")),
                    target = normalizedTarget(item.optString("target")),
                    mood = normalizedMood(item.optString("mood")),
                )
            }
            "circle" -> CanvasCommand.Circle(
                anchor = normalizedAnchor(item.optString("anchor")),
                size = normalizedSize(item.optString("size")),
                target = normalizedTarget(item.optString("target")),
                mood = normalizedMood(item.optString("mood")),
            )
            "arrow" -> CanvasCommand.Arrow(
                from = normalizedDirection(item.optString("from"), "left"),
                to = normalizedAnchor(item.optString("to")),
                target = normalizedTarget(item.optString("target")),
                mood = normalizedMood(item.optString("mood")),
            )
            "underline" -> CanvasCommand.Underline(
                anchor = normalizedAnchor(item.optString("anchor")),
                target = normalizedTarget(item.optString("target")),
                mood = normalizedMood(item.optString("mood")),
            )
            "dot" -> CanvasCommand.Dot(
                anchor = normalizedAnchor(item.optString("anchor")),
                target = normalizedTarget(item.optString("target")),
                mood = normalizedMood(item.optString("mood")),
            )
            "scribble", "bracket", "strike", "spark", "question_mark", "small_note",
            "speech_bubble", "burst", "emphasis_lines", "reaction_mark" -> CanvasCommand.Mark(
                type = item.optString("type"),
                text = item.optString("text").trim(),
                anchor = normalizedAnchor(item.optString("anchor")),
                size = normalizedSize(item.optString("size")),
                rotate = item.optDouble("rotate", 0.0).toFloat().coerceIn(-14f, 14f),
                target = normalizedTarget(item.optString("target")),
                mood = normalizedMood(item.optString("mood")),
            )
            else -> null
        }
    }

    private fun extractFragments(parsed: JSONObject): List<String> {
        val fragments = parsed.optJSONArray("fragments") ?: return emptyList()
        return buildList {
            for (index in 0 until fragments.length()) {
                val fragment = fragments.optString(index).trim()
                if (fragment.isNotEmpty()) add(fragment)
            }
        }.take(3)
    }

    private fun normalizedAnchor(value: String): String {
        return when (value) {
            "above_input", "below_input", "left_of_input", "right_of_input", "on_input", "paper_margin",
            "top_left", "top_right", "center", "bottom_left", "bottom_right" -> value
            else -> "below_input"
        }
    }

    private fun normalizedDirection(value: String, fallback: String): String {
        return when (value) {
            "left", "right", "top", "bottom", "top_left", "top_right", "bottom_left", "bottom_right", "center" -> value
            else -> fallback
        }
    }

    private fun normalizedSize(value: String): String {
        return when (value) {
            "small", "medium", "large" -> value
            else -> "medium"
        }
    }

    private fun normalizedTextStyle(value: String): String {
        return when (value) {
            "answer", "annotation" -> value
            else -> "answer"
        }
    }

    private fun normalizedTarget(value: String): String {
        return when (value) {
            "input", "paper" -> value
            else -> "input"
        }
    }

    private fun normalizedMood(value: String): String {
        return when (value) {
            "quiet", "curious", "sharp", "playful" -> value
            else -> "quiet"
        }
    }

    private fun sanitizeNormalizedText(raw: String): String {
        var sanitized = removeThinkingBlocks(raw).trim()
        sanitized = sanitized.removeSurrounding("```").trim()
        sanitized = sanitized.removePrefix("```text").trim()
        sanitized = sanitized.removePrefix("```txt").trim()
        sanitized = sanitized.removeSuffix("```").trim()
        sanitized = sanitized.removeSurrounding("\"").trim()
        sanitized = sanitized.removeSurrounding("“", "”").trim()
        OBSERVATION_PREFIXES.firstOrNull { sanitized.startsWith(it, ignoreCase = true) }?.let { prefix ->
            sanitized = sanitized.removePrefix(prefix).trim()
        }
        sanitized = sanitized
            .lineSequence()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .joinToString(" ")
        return sanitized.ifEmpty { FALLBACK_NORMALIZED_TEXT }
    }

    private fun classifyImageNormalization(text: String): String {
        if (text == FALLBACK_NORMALIZED_TEXT) return "unclear"
        return if (looksLikeMostlyText(text)) "image_text" else "image_scene"
    }

    private fun classifyAudioNormalization(text: String): String {
        if (text == FALLBACK_NORMALIZED_TEXT) return "unclear"
        return if (looksLikeMostlyText(text)) "audio_transcript" else "audio_summary"
    }

    private fun looksLikeMostlyText(text: String): Boolean {
        if (text.isBlank()) return false
        if (text.length >= 8) return true
        return text.any { it.isLetterOrDigit() || it.code > 0x2E80 }
    }

    private fun removeThinkingBlocks(text: String): String {
        return Regex(
            """<think\b[^>]*>.*?</think>""",
            setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
        ).replace(text, "").trim()
    }

    private fun extractJson(text: String): JSONObject {
        try {
            val parsed = JSONObject(text)
            if (isTopLevelResponse(parsed)) return parsed
        } catch (_: Exception) {
        }

        for (start in text.indices) {
            if (text[start] != '{') continue
            for (end in text.lastIndex downTo start) {
                if (text[end] != '}') continue
                try {
                    val parsed = JSONObject(text.substring(start, end + 1))
                    if (isTopLevelResponse(parsed)) return parsed
                } catch (_: Exception) {
                }
            }
        }

        throw IllegalArgumentException("Model did not return valid JSON: $text")
    }

    private fun isTopLevelResponse(parsed: JSONObject): Boolean {
        return parsed.has("canvas") ||
            parsed.has("recognized_text") ||
            parsed.has("answer_text") ||
            parsed.has("fragments") ||
            parsed.optString("action") == "stay_silent"
    }

    private fun debugLog(message: String) {
        if (BuildConfig.DEBUG) {
            Log.d(TAG, message)
        }
    }

    override fun close() {
        if (::engine.isInitialized) {
            engine.close()
        }
    }
}

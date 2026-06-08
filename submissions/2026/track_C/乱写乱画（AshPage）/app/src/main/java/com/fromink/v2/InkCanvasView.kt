package com.fromink.v2

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PointF
import android.graphics.RectF
import android.graphics.Typeface
import android.os.SystemClock
import android.view.MotionEvent
import android.view.View
import java.io.ByteArrayOutputStream
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.cos
import kotlin.math.PI
import kotlin.random.Random

class InkCanvasView(context: Context) : View(context) {
    var onStrokeStarted: (() -> Unit)? = null
    var onStrokeEnded: (() -> Unit)? = null

    private val strokes = mutableListOf<MutableList<PointF>>()
    private val renderedElements = mutableListOf<CanvasElement>()
    private val overlayElements = mutableListOf<CanvasElement>()
    private var currentStroke: MutableList<PointF>? = null
    private var lastInputBounds: RectF? = null
    private var waitingEffectActive = false
    private var waitingEffectStartedAt = 0L
    private var clearOnNextStrokeStart = false

    private val answerChineseTypeface = loadTypeface("fonts/MaShanZheng-Regular.ttf")
        ?: loadTypeface("fonts/LiuJianMaoCao-Regular.ttf")
        ?: Typeface.create(Typeface.SERIF, Typeface.NORMAL)
    private val annotationChineseTypeface = answerChineseTypeface
    private val answerLatinTypeface = loadTypeface("fonts/Caveat-Regular.ttf")
        ?: Typeface.create(Typeface.SERIF, Typeface.NORMAL)
    private val annotationLatinTypeface = answerLatinTypeface

    private val inkPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF1F1A17.toInt()
        strokeWidth = 5f
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    private val dotPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF35251F.toInt()
        style = Paint.Style.FILL
    }
    private val paperPaint = Paint().apply {
        color = 0xFFECE3C3.toInt()
        style = Paint.Style.FILL
    }
    private val paperEdgePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0x332A1F12
        strokeWidth = 1.5f
        style = Paint.Style.STROKE
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFF35251F.toInt()
        style = Paint.Style.FILL
    }
    private val doodlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xCC35251F.toInt()
        strokeWidth = 3.4f
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }

    init {
        setBackgroundColor(0xFFECE3C3.toInt())
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        drawPaper(canvas)
        for (stroke in strokes) drawStroke(canvas, stroke)
        currentStroke?.let { drawStroke(canvas, it) }
        for (element in renderedElements) drawElement(canvas, element)
        for (element in overlayElements) drawElement(canvas, element)
        if (waitingEffectActive) drawWaitingEffect(canvas)
        if (waitingEffectActive) postInvalidateOnAnimation()
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        val point = PointF(event.x, event.y)
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                onStrokeStarted?.invoke()
                if (clearOnNextStrokeStart) {
                    resetForNextSession()
                } else {
                    clearRenderedResponse()
                }
                currentStroke = mutableListOf(point)
                invalidate()
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                currentStroke?.add(point)
                invalidate()
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                var addedStroke = false
                currentStroke?.let {
                    if (it.isNotEmpty()) {
                        strokes.add(it)
                        addedStroke = true
                    }
                }
                currentStroke = null
                invalidate()
                if (addedStroke) onStrokeEnded?.invoke()
                return true
            }
        }
        return false
    }

    fun hasInk(): Boolean = strokes.isNotEmpty() || currentStroke?.isNotEmpty() == true

    fun undo() {
        if (strokes.isNotEmpty()) {
            strokes.removeAt(strokes.lastIndex)
            invalidate()
        }
    }

    fun clearAll() {
        stopWaitingEffect()
        strokes.clear()
        currentStroke = null
        lastInputBounds = null
        renderedElements.clear()
        overlayElements.clear()
        clearOnNextStrokeStart = false
        invalidate()
    }

    fun showWaitingWave() {
        renderedElements.clear()
        overlayElements.clear()
        waitingEffectActive = true
        waitingEffectStartedAt = SystemClock.uptimeMillis()
        invalidate()
    }

    fun showSilentDot() {
        stopWaitingEffect()
        overlayElements.clear()
        renderedElements.clear()
        renderedElements.add(DotElement(58f, 120f, 3.2f, 1f))
        clearOnNextStrokeStart = true
        invalidate()
    }

    fun showAnnotation(message: String) {
        stopWaitingEffect()
        overlayElements.clear()
        renderedElements.clear()
        renderedElements.add(
            TextElement(
                content = message,
                x = 40f,
                y = 118f,
                style = TextStyle.ANNOTATION,
                rotate = -2f,
                maxWidth = max(width - 80f, 180f),
                textSize = 30f,
            ),
        )
        clearOnNextStrokeStart = true
        invalidate()
    }

    fun showAnswerFragments(fragments: List<String>) {
        stopWaitingEffect()
        overlayElements.clear()
        renderedElements.clear()
        val anchors = shuffledAnchors()
        fragments.take(3).forEachIndexed { index, fragment ->
            renderedElements.add(createFragmentElement(fragment, index, anchors))
        }
        clearOnNextStrokeStart = true
        invalidate()
    }

    fun showCanvasCommands(commands: List<CanvasCommand>) {
        stopWaitingEffect()
        overlayElements.clear()
        renderedElements.clear()
        if (commands.isEmpty()) {
            showSilentDot()
            return
        }

        renderedElements.addAll(layoutCanvasCommands(commands.take(6)))
        clearOnNextStrokeStart = true
        invalidate()
    }

    fun toPngBytes(): ByteArray {
        val bitmapWidth = max(width, 1)
        val bitmapHeight = max(height, 1)
        lastInputBounds = computeInkBounds()
        val bitmap = Bitmap.createBitmap(bitmapWidth, bitmapHeight, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        drawPaper(canvas, bitmapWidth.toFloat(), bitmapHeight.toFloat())
        for (stroke in strokes) drawStroke(canvas, stroke)
        currentStroke?.let { drawStroke(canvas, it) }

        return ByteArrayOutputStream().use { output ->
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)
            bitmap.recycle()
            output.toByteArray()
        }
    }

    private fun clearRenderedResponse() {
        stopWaitingEffect()
        renderedElements.clear()
        overlayElements.clear()
    }

    private fun resetForNextSession() {
        stopWaitingEffect()
        strokes.clear()
        currentStroke = null
        lastInputBounds = null
        renderedElements.clear()
        overlayElements.clear()
        clearOnNextStrokeStart = false
    }

    private fun stopWaitingEffect() {
        waitingEffectActive = false
        waitingEffectStartedAt = 0L
    }

    private fun drawPaper(canvas: Canvas, paperWidth: Float = width.toFloat(), paperHeight: Float = height.toFloat()) {
        canvas.drawRect(0f, 0f, paperWidth, paperHeight, paperPaint)
        canvas.drawRect(1f, 1f, paperWidth - 1f, paperHeight - 1f, paperEdgePaint)
    }

    private fun drawStroke(canvas: Canvas, stroke: List<PointF>) {
        if (stroke.isEmpty()) return
        if (stroke.size == 1) {
            val point = stroke[0]
            canvas.drawCircle(point.x, point.y, inkPaint.strokeWidth / 2f, dotPaint)
            return
        }

        val path = Path().apply {
            moveTo(stroke[0].x, stroke[0].y)
            for (index in 1 until stroke.size) lineTo(stroke[index].x, stroke[index].y)
        }
        canvas.drawPath(path, inkPaint)
    }

    private fun drawElement(canvas: Canvas, element: CanvasElement) {
        when (element) {
            is DotElement -> {
                dotPaint.alpha = (element.alpha * 255).toInt().coerceIn(0, 255)
                canvas.drawCircle(element.x, element.y, element.radius, dotPaint)
                dotPaint.alpha = 255
            }
            is TextElement -> drawTextElement(canvas, element)
            is CircleElement -> drawCircleElement(canvas, element)
            is ArrowElement -> drawArrowElement(canvas, element)
            is UnderlineElement -> drawUnderlineElement(canvas, element)
            is PathElement -> drawPathElement(canvas, element)
            is BubbleElement -> drawBubbleElement(canvas, element)
            is BurstElement -> drawBurstElement(canvas, element)
        }
    }

    private fun drawWaitingEffect(canvas: Canvas) {
        val elapsed = (SystemClock.uptimeMillis() - waitingEffectStartedAt) / 1000f
        val baseX = width - 92f
        val baseY = 56f
        val gap = 16f
        val baseRadius = 2.6f

        for (index in 0..2) {
            val phase = elapsed * 3.0f + index * 0.72f
            val wave = sin(phase)
            val alpha = (0.22f + ((wave + 1f) * 0.2f)).coerceIn(0.16f, 0.62f)
            val y = baseY + wave * 3.2f
            val radius = baseRadius + ((wave + 1f) * 0.4f)
            dotPaint.alpha = (alpha * 255).toInt().coerceIn(0, 255)
            dotPaint.color = 0xAA7B5D49.toInt()
            canvas.drawCircle(baseX + (index - 1) * gap, y, radius, dotPaint)
        }
        dotPaint.color = 0xFF35251F.toInt()
        dotPaint.alpha = 255
    }

    private fun drawTextElement(canvas: Canvas, element: TextElement) {
        canvas.save()
        configureTextPaint(element.style, element.textSize, element.content)
        canvas.translate(element.x, element.y)
        canvas.rotate(element.rotate)
        wrapText(canvas, element.content, element.maxWidth, lineHeightForStyle(element.style))
        canvas.restore()
    }

    private fun wrapText(canvas: Canvas, text: String, maxWidth: Float, lineHeight: Float) {
        var offsetY = 0f
        for (paragraph in text.split("\n")) {
            var line = ""
            for (char in paragraph) {
                val testLine = line + char
                if (textPaint.measureText(testLine) > maxWidth && line.isNotEmpty()) {
                    drawHandwrittenLine(canvas, line, offsetY)
                    line = char.toString()
                    offsetY += lineHeight
                } else {
                    line = testLine
                }
            }
            if (line.isNotEmpty()) {
                drawHandwrittenLine(canvas, line, offsetY)
                offsetY += lineHeight
            }
        }
    }

    private fun drawHandwrittenLine(canvas: Canvas, line: String, y: Float) {
        val jitterX = (Random.nextFloat() - 0.5f) * 2.4f
        val jitterY = (Random.nextFloat() - 0.5f) * 2f
        canvas.drawText(line, jitterX, y + jitterY, textPaint)
    }

    private fun lineHeightForStyle(style: TextStyle): Float = when (style) {
        TextStyle.ANSWER -> 66f
        TextStyle.ANNOTATION -> 46f
        TextStyle.QUESTION -> 54f
    }

    private fun drawCircleElement(canvas: Canvas, element: CircleElement) {
        canvas.save()
        doodlePaint.alpha = 190
        doodlePaint.strokeWidth = 3.2f
        canvas.rotate(element.rotate, element.centerX, element.centerY)
        val path = Path()
        val steps = 52
        for (index in 0..steps) {
            val angle = (index.toFloat() / steps.toFloat()) * (PI.toFloat() * 2f)
            val wobble = 1f + sin(angle * 3.1f + element.wobbleSeed) * 0.035f
            val x = element.centerX + cos(angle) * element.radiusX * wobble
            val y = element.centerY + sin(angle) * element.radiusY * wobble
            if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        canvas.drawPath(path, doodlePaint)
        doodlePaint.alpha = 255
        canvas.restore()
    }

    private fun drawArrowElement(canvas: Canvas, element: ArrowElement) {
        doodlePaint.alpha = 185
        doodlePaint.strokeWidth = 3.0f
        val controlX = (element.startX + element.endX) / 2f + element.curve
        val controlY = (element.startY + element.endY) / 2f - element.curve * 0.4f
        val path = Path().apply {
            moveTo(element.startX, element.startY)
            quadTo(controlX, controlY, element.endX, element.endY)
        }
        canvas.drawPath(path, doodlePaint)

        val angle = kotlin.math.atan2(element.endY - controlY, element.endX - controlX)
        val headLength = 18f
        val left = angle + 2.55f
        val right = angle - 2.55f
        canvas.drawLine(
            element.endX,
            element.endY,
            element.endX + cos(left) * headLength,
            element.endY + sin(left) * headLength,
            doodlePaint,
        )
        canvas.drawLine(
            element.endX,
            element.endY,
            element.endX + cos(right) * headLength,
            element.endY + sin(right) * headLength,
            doodlePaint,
        )
        doodlePaint.alpha = 255
    }

    private fun drawUnderlineElement(canvas: Canvas, element: UnderlineElement) {
        doodlePaint.alpha = 175
        doodlePaint.strokeWidth = 3.2f
        val path = Path().apply {
            moveTo(element.startX, element.y)
            cubicTo(
                element.startX + element.width * 0.28f,
                element.y + element.wave,
                element.startX + element.width * 0.62f,
                element.y - element.wave,
                element.startX + element.width,
                element.y + element.wave * 0.4f,
            )
        }
        canvas.drawPath(path, doodlePaint)
        doodlePaint.alpha = 255
    }

    private fun drawPathElement(canvas: Canvas, element: PathElement) {
        doodlePaint.alpha = element.alpha
        doodlePaint.strokeWidth = element.strokeWidth
        canvas.drawPath(element.path, doodlePaint)
        doodlePaint.alpha = 255
    }

    private fun drawBubbleElement(canvas: Canvas, element: BubbleElement) {
        canvas.save()
        doodlePaint.alpha = 170
        doodlePaint.strokeWidth = 3.0f
        canvas.rotate(element.rotate, element.rect.centerX(), element.rect.centerY())
        val path = roundedWobbleRect(element.rect, 16f, element.seed)
        canvas.drawPath(path, doodlePaint)
        val tailX = element.rect.left + element.rect.width() * 0.26f
        val tailY = element.rect.bottom - 2f
        val tail = Path().apply {
            moveTo(tailX, tailY)
            lineTo(tailX - 15f, tailY + 22f)
            lineTo(tailX + 18f, tailY + 5f)
        }
        canvas.drawPath(tail, doodlePaint)
        doodlePaint.alpha = 255
        canvas.restore()
    }

    private fun drawBurstElement(canvas: Canvas, element: BurstElement) {
        doodlePaint.alpha = 185
        doodlePaint.strokeWidth = 2.8f
        val rays = 10
        for (index in 0 until rays) {
            val angle = (index.toFloat() / rays.toFloat()) * PI.toFloat() * 2f + element.rotate
            val inner = element.radius * if (index % 2 == 0) 0.48f else 0.68f
            val outer = element.radius * (0.9f + stableUnit(element.seed + index) * 0.22f)
            canvas.drawLine(
                element.x + cos(angle) * inner,
                element.y + sin(angle) * inner,
                element.x + cos(angle) * outer,
                element.y + sin(angle) * outer,
                doodlePaint,
            )
        }
        doodlePaint.alpha = 255
    }

    private fun shuffledAnchors(): List<PointF> {
        val canvasWidth = max(width.toFloat(), 320f)
        val canvasHeight = max(height.toFloat(), 320f)
        val marginX = min(72f, canvasWidth * 0.14f)
        val marginY = min(72f, canvasHeight * 0.14f)
        return listOf(
            PointF(marginX, marginY),
            PointF(canvasWidth * 0.52f, marginY + 10f),
            PointF(canvasWidth * 0.2f, canvasHeight * 0.34f),
            PointF(canvasWidth * 0.62f, canvasHeight * 0.36f),
            PointF(canvasWidth * 0.12f, canvasHeight * 0.6f),
            PointF(canvasWidth * 0.56f, canvasHeight * 0.62f),
        ).shuffled()
    }

    private fun createFragmentElement(content: String, index: Int, anchors: List<PointF>): TextElement {
        val canvasWidth = max(width.toFloat(), 320f)
        val canvasHeight = max(height.toFloat(), 320f)
        val anchor = anchors.getOrNull(index) ?: PointF(
            canvasWidth * (0.18f + Random.nextFloat() * 0.5f),
            canvasHeight * (0.18f + Random.nextFloat() * 0.52f),
        )
        val x = max(24f, min(anchor.x + ((Random.nextFloat() - 0.5f) * 28f), canvasWidth - 180f))
        val y = max(24f, min(anchor.y + ((Random.nextFloat() - 0.5f) * 34f), canvasHeight - 90f))
        val maxWidth = max(min(canvasWidth * 0.34f, canvasWidth - 120f), 150f)
        return TextElement(
            content = content,
            x = x,
            y = y,
            style = TextStyle.ANSWER,
            rotate = ((Random.nextFloat() - 0.5f) * 10f),
            maxWidth = maxWidth,
            textSize = 52f,
        )
    }

    private fun layoutCanvasCommands(commands: List<CanvasCommand>): List<CanvasElement> {
        val inputBounds = layoutInputBounds()
        val inputProtection = expandedRect(inputBounds, 18f, 16f)
        val occupiedRects = mutableListOf(controlAvoidRect())
        val placed = mutableListOf<CanvasElement>()
        var primaryTextPlaced = false

        for ((index, command) in commands.sortedBy { commandPriority(it) }.withIndex()) {
            if (command is CanvasCommand.Text && primaryTextPlaced) {
                continue
            }
            val placedElement = placeCommand(command, index, inputBounds, inputProtection, occupiedRects)
            if (placedElement != null) {
                placed.add(placedElement)
                occupiedRects.add(expandedRect(measureBounds(placedElement), 10f, 8f))
                if (command is CanvasCommand.Text) {
                    primaryTextPlaced = true
                }
            }
        }

        return placed
    }

    private fun placeCommand(
        command: CanvasCommand,
        index: Int,
        inputBounds: RectF,
        inputProtection: RectF,
        occupiedRects: MutableList<RectF>,
    ): CanvasElement? {
        val seed = stableSeed(index, command)
        val slotOptions = slotPreferencesFor(command)
        val sizeOptions = sizePreferencesFor(command)
        val allowInputOverlap = command.allowsInputOverlap()

        for (size in sizeOptions) {
            for (slot in slotOptions) {
                for (offset in offsetsFor(slot)) {
                    val candidate = PlacementCandidate(slot, size, offset.x, offset.y)
                    val element = command.toElement(candidate, seed, inputBounds)
                    val bounds = measureBounds(element)
                    if (!isInSafeArea(bounds)) continue
                    if (!allowInputOverlap && RectF.intersects(bounds, inputProtection)) continue
                    if (occupiedRects.any { RectF.intersects(bounds, it) }) continue
                    return element
                }
            }
        }
        return null
    }

    private fun CanvasCommand.toElement(candidate: PlacementCandidate, seed: Int, inputBounds: RectF): CanvasElement {
        val point = pointForSlot(candidate.slot, inputBounds, seed, candidate.offsetX, candidate.offsetY)
        return when (this) {
            is CanvasCommand.Text -> {
                val textSize = textSizeFor(candidate.size, style)
                val maxWidth = maxWidthForSlot(candidate.slot, style)
                TextElement(
                    content = text,
                    x = point.x,
                    y = point.y,
                    style = if (style == "annotation") TextStyle.ANNOTATION else TextStyle.ANSWER,
                    rotate = rotate.coerceIn(-14f, 14f),
                    maxWidth = maxWidth,
                    textSize = textSize,
                )
            }
            is CanvasCommand.Circle -> {
                val radius = circleSizeFor(candidate.size, inputBounds)
                CircleElement(
                    centerX = point.x,
                    centerY = point.y,
                    radiusX = radius.x,
                    radiusY = radius.y,
                    rotate = stableOffset(seed, 2, 9f),
                    wobbleSeed = stableUnit(seed + 3) * 10f,
                )
            }
            is CanvasCommand.Arrow -> {
                val start = pointForDirection(normalizedDirectionForArrow(from), inputBounds, seed)
                val end = pointForSlot(slotForArrowTarget(to), inputBounds, seed + 11, candidate.offsetX * 0.4f, candidate.offsetY * 0.4f)
                ArrowElement(
                    startX = start.x,
                    startY = start.y,
                    endX = end.x,
                    endY = end.y,
                    curve = stableOffset(seed, 4, 36f),
                )
            }
            is CanvasCommand.Underline -> {
                val lineWidth = underlineWidthFor(inputBounds)
                UnderlineElement(
                    startX = clamp(inputBounds.left - 8f, 24f, width - lineWidth - 24f),
                    y = clamp(inputBounds.bottom + 12f + candidate.offsetY * 0.2f, 50f, height - 42f),
                    width = lineWidth,
                    wave = 5f + stableUnit(seed + 2) * 5f,
                )
            }
            is CanvasCommand.Dot -> {
                DotElement(
                    x = point.x,
                    y = point.y,
                    radius = 3.2f + stableUnit(seed + 2) * 2.2f,
                    alpha = 0.85f,
                )
            }
            is CanvasCommand.Mark -> markToElement(this, candidate, seed, inputBounds)
        }
    }

    private fun markToElement(
        command: CanvasCommand.Mark,
        candidate: PlacementCandidate,
        seed: Int,
        inputBounds: RectF,
    ): CanvasElement {
        val point = pointForSlot(candidate.slot, inputBounds, seed, candidate.offsetX, candidate.offsetY)
        val size = doodleScalarFor(candidate.size)
        return when (command.type) {
            "small_note" -> TextElement(
                content = command.text.ifBlank { "留意这里。" },
                x = point.x,
                y = point.y,
                style = TextStyle.ANNOTATION,
                rotate = command.rotate.coerceIn(-14f, 14f),
                maxWidth = maxWidthForSlot(candidate.slot, "annotation"),
                textSize = textSizeFor(candidate.size, "annotation"),
            )
            "speech_bubble" -> {
                val rect = RectF(
                    clamp(point.x - size * 0.9f, 24f, width - size * 2.1f - 24f),
                    clamp(point.y - size * 0.45f, 30f, height - size * 1.18f - 48f),
                    0f,
                    0f,
                )
                rect.right = rect.left + size * 2.1f
                rect.bottom = rect.top + size * 1.18f
                BubbleElement(rect, command.rotate.coerceIn(-10f, 10f), seed)
            }
            "burst" -> BurstElement(
                x = point.x,
                y = point.y,
                radius = size * 0.62f,
                rotate = stableOffset(seed, 2, 0.4f),
                seed = seed,
            )
            "spark", "reaction_mark", "question_mark" -> createSparkLikeElement(command, point, size, seed)
            "bracket" -> createBracketElement(point, size, seed)
            "scribble" -> createScribbleElement(point, size, seed)
            "strike" -> createStrikeElement(point, size, seed)
            "emphasis_lines" -> createEmphasisElement(point, size, seed)
            else -> createSparkLikeElement(command, point, size, seed + 17)
        }
    }

    private fun createSparkLikeElement(
        command: CanvasCommand.Mark,
        point: PointF,
        size: Float,
        seed: Int,
    ): CanvasElement {
        if (command.type == "question_mark") {
            return TextElement(
                content = "?",
                x = clamp(point.x + stableOffset(seed, 0, 22f), 28f, width - 80f),
                y = clamp(point.y + stableOffset(seed, 1, 22f), 34f, height - 80f),
                style = TextStyle.ANNOTATION,
                rotate = command.rotate.coerceIn(-14f, 14f),
                maxWidth = 80f,
                textSize = size * 0.72f,
            )
        }

        val path = Path()
        val cx = clamp(point.x + stableOffset(seed, 0, 22f), 34f, width - 34f)
        val cy = clamp(point.y + stableOffset(seed, 1, 22f), 34f, height - 48f)
        val rays = if (command.type == "reaction_mark") 3 else 4
        for (i in 0 until rays) {
            val angle = (i.toFloat() / rays) * PI.toFloat() * 2f + stableOffset(seed, i, 0.3f)
            val inner = size * 0.12f
            val outer = size * 0.34f
            path.moveTo(cx + cos(angle) * inner, cy + sin(angle) * inner)
            path.lineTo(cx + cos(angle) * outer, cy + sin(angle) * outer)
        }
        return PathElement(path, 2.6f, 185)
    }

    private fun createBracketElement(point: PointF, size: Float, seed: Int): CanvasElement {
        val x = clamp(point.x + stableOffset(seed, 0, 18f), 28f, width - 48f)
        val y = clamp(point.y + stableOffset(seed, 1, 18f), 32f, height - size - 40f)
        val path = Path().apply {
            moveTo(x + size * 0.42f, y)
            cubicTo(x + size * 0.1f, y + size * 0.12f, x, y + size * 0.32f, x + size * 0.18f, y + size * 0.5f)
            cubicTo(x, y + size * 0.7f, x + size * 0.12f, y + size * 0.9f, x + size * 0.45f, y + size)
        }
        return PathElement(path, 3.2f, 180)
    }

    private fun createScribbleElement(point: PointF, size: Float, seed: Int): CanvasElement {
        val x = clamp(point.x - size * 0.45f, 24f, width - size - 24f)
        val y = clamp(point.y + stableOffset(seed, 0, 20f), 34f, height - 52f)
        val path = Path().apply {
            moveTo(x, y)
            for (i in 1..7) {
                val px = x + size * (i / 7f)
                val py = y + stableOffset(seed, i, size * 0.38f)
                lineTo(px, py)
            }
        }
        return PathElement(path, 3.0f, 170)
    }

    private fun createStrikeElement(point: PointF, size: Float, seed: Int): CanvasElement {
        val x = clamp(point.x - size * 0.55f, 24f, width - size - 24f)
        val y = clamp(point.y + stableOffset(seed, 0, 18f), 34f, height - 52f)
        val path = Path().apply {
            moveTo(x, y)
            cubicTo(x + size * 0.28f, y - 6f, x + size * 0.62f, y + 8f, x + size, y)
        }
        return PathElement(path, 3.4f, 190)
    }

    private fun createEmphasisElement(point: PointF, size: Float, seed: Int): CanvasElement {
        val path = Path()
        val cx = clamp(point.x + stableOffset(seed, 0, 20f), 34f, width - 34f)
        val cy = clamp(point.y + stableOffset(seed, 1, 20f), 34f, height - 52f)
        for (i in 0..2) {
            val dx = (i - 1) * size * 0.18f
            path.moveTo(cx + dx, cy)
            path.lineTo(cx + dx + stableOffset(seed, i + 3, 8f), cy - size * 0.45f)
        }
        return PathElement(path, 2.8f, 180)
    }

    private fun commandPriority(command: CanvasCommand): Int {
        return when (command) {
            is CanvasCommand.Text -> 0
            is CanvasCommand.Underline, is CanvasCommand.Circle -> 1
            is CanvasCommand.Mark -> when (command.type) {
                "bracket", "strike" -> 1
                "small_note", "speech_bubble" -> 2
                else -> 3
            }
            is CanvasCommand.Arrow -> 3
            is CanvasCommand.Dot -> 4
        }
    }

    private fun slotPreferencesFor(command: CanvasCommand): List<LayoutSlot> {
        return when (command) {
            is CanvasCommand.Text -> listOf(slotForAnchor(command.anchor), LayoutSlot.BELOW_INPUT, LayoutSlot.RIGHT_OF_INPUT, LayoutSlot.ABOVE_INPUT)
            is CanvasCommand.Circle, is CanvasCommand.Underline -> listOf(LayoutSlot.ON_INPUT)
            is CanvasCommand.Arrow -> listOf(LayoutSlot.RIGHT_OF_INPUT, LayoutSlot.LEFT_OF_INPUT, LayoutSlot.ABOVE_INPUT)
            is CanvasCommand.Dot -> listOf(LayoutSlot.PAPER_MARGIN, LayoutSlot.TOP_LEFT)
            is CanvasCommand.Mark -> when (command.type) {
                "bracket", "strike" -> listOf(LayoutSlot.ON_INPUT)
                "small_note" -> listOf(LayoutSlot.RIGHT_OF_INPUT, LayoutSlot.BELOW_INPUT, LayoutSlot.PAPER_MARGIN)
                "speech_bubble" -> listOf(LayoutSlot.RIGHT_OF_INPUT, LayoutSlot.LEFT_OF_INPUT)
                "question_mark", "reaction_mark", "spark", "emphasis_lines" -> listOf(
                    LayoutSlot.ABOVE_INPUT,
                    LayoutSlot.RIGHT_OF_INPUT,
                    LayoutSlot.LEFT_OF_INPUT,
                    LayoutSlot.TOP_RIGHT,
                    LayoutSlot.TOP_LEFT,
                )
                else -> listOf(LayoutSlot.RIGHT_OF_INPUT, LayoutSlot.ABOVE_INPUT, LayoutSlot.PAPER_MARGIN)
            }
        }.distinct()
    }

    private fun sizePreferencesFor(command: CanvasCommand): List<String> {
        val initial = when (command) {
            is CanvasCommand.Text -> normalizedSizeLabel(command.size)
            is CanvasCommand.Circle -> normalizedSizeLabel(command.size)
            is CanvasCommand.Mark -> normalizedSizeLabel(command.size)
            else -> "medium"
        }
        return when (initial) {
            "large" -> listOf("large", "medium", "small")
            "small" -> listOf("small", "medium")
            else -> listOf("medium", "small")
        }
    }

    private fun CanvasCommand.allowsInputOverlap(): Boolean {
        return when (this) {
            is CanvasCommand.Circle, is CanvasCommand.Underline -> true
            is CanvasCommand.Mark -> type in setOf("bracket", "strike")
            else -> false
        }
    }

    private fun offsetsFor(slot: LayoutSlot): List<PointF> {
        return when (slot) {
            LayoutSlot.ON_INPUT -> listOf(
                PointF(0f, 0f),
                PointF(0f, 10f),
                PointF(0f, -8f),
            )
            LayoutSlot.ABOVE_INPUT, LayoutSlot.BELOW_INPUT -> listOf(
                PointF(0f, 0f),
                PointF(-26f, 0f),
                PointF(26f, 0f),
                PointF(-18f, -16f),
                PointF(18f, 16f),
            )
            LayoutSlot.LEFT_OF_INPUT, LayoutSlot.RIGHT_OF_INPUT -> listOf(
                PointF(0f, 0f),
                PointF(0f, -22f),
                PointF(0f, 22f),
                PointF(0f, -40f),
                PointF(0f, 40f),
            )
            LayoutSlot.PAPER_MARGIN, LayoutSlot.TOP_LEFT, LayoutSlot.TOP_RIGHT, LayoutSlot.BOTTOM_LEFT, LayoutSlot.BOTTOM_RIGHT -> listOf(
                PointF(0f, 0f),
                PointF(22f, 0f),
                PointF(-22f, 0f),
                PointF(0f, 16f),
            )
            LayoutSlot.CENTER -> listOf(PointF(0f, 0f))
        }
    }

    private fun pointForSlot(
        slot: LayoutSlot,
        inputBounds: RectF,
        seed: Int,
        offsetX: Float,
        offsetY: Float,
    ): PointF {
        val safeWidth = max(width.toFloat(), 320f)
        val safeHeight = max(height.toFloat(), 320f)
        val gapX = min(54f, safeWidth * 0.11f)
        val gapY = min(46f, safeHeight * 0.09f)
        val base = when (slot) {
            LayoutSlot.ON_INPUT -> PointF(inputBounds.centerX(), inputBounds.centerY())
            LayoutSlot.ABOVE_INPUT -> PointF(inputBounds.centerX(), inputBounds.top - gapY)
            LayoutSlot.BELOW_INPUT -> PointF(inputBounds.centerX(), inputBounds.bottom + gapY)
            LayoutSlot.LEFT_OF_INPUT -> PointF(inputBounds.left - gapX, inputBounds.centerY())
            LayoutSlot.RIGHT_OF_INPUT -> PointF(inputBounds.right + gapX, inputBounds.centerY())
            LayoutSlot.PAPER_MARGIN -> PointF(safeWidth * 0.18f, safeHeight * 0.16f)
            LayoutSlot.TOP_LEFT -> PointF(safeWidth * 0.16f, safeHeight * 0.18f)
            LayoutSlot.TOP_RIGHT -> PointF(safeWidth * 0.7f, safeHeight * 0.18f)
            LayoutSlot.BOTTOM_LEFT -> PointF(safeWidth * 0.16f, safeHeight * 0.62f)
            LayoutSlot.BOTTOM_RIGHT -> PointF(safeWidth * 0.68f, safeHeight * 0.62f)
            LayoutSlot.CENTER -> PointF(safeWidth * 0.5f, safeHeight * 0.38f)
        }
        return clampPoint(
            PointF(
                base.x + offsetX + stableOffset(seed, slot.ordinal + 1, 8f),
                base.y + offsetY + stableOffset(seed, slot.ordinal + 17, 8f),
            ),
        )
    }

    private fun pointForDirection(direction: String, inputBounds: RectF, seed: Int): PointF {
        val safeWidth = max(width.toFloat(), 320f)
        val safeHeight = max(height.toFloat(), 320f)
        return when (direction) {
            "left" -> PointF(inputBounds.left - 70f + stableOffset(seed, 0, 12f), inputBounds.centerY())
            "right" -> PointF(inputBounds.right + 70f + stableOffset(seed, 1, 12f), inputBounds.centerY())
            "top" -> PointF(inputBounds.centerX(), inputBounds.top - 64f + stableOffset(seed, 2, 12f))
            "bottom" -> PointF(inputBounds.centerX(), inputBounds.bottom + 64f + stableOffset(seed, 3, 12f))
            "top_left" -> PointF(safeWidth * 0.18f, safeHeight * 0.18f)
            "top_right" -> PointF(safeWidth * 0.72f, safeHeight * 0.18f)
            "bottom_left" -> PointF(safeWidth * 0.18f, safeHeight * 0.62f)
            "bottom_right" -> PointF(safeWidth * 0.72f, safeHeight * 0.62f)
            else -> pointForSlot(slotForAnchor(direction), inputBounds, seed, 0f, 0f)
        }.let { clampPoint(it) }
    }

    private fun slotForArrowTarget(anchor: String): LayoutSlot = slotForAnchor(anchor)

    private fun slotForAnchor(anchor: String): LayoutSlot {
        return when (anchor) {
            "above_input" -> LayoutSlot.ABOVE_INPUT
            "below_input" -> LayoutSlot.BELOW_INPUT
            "left_of_input" -> LayoutSlot.LEFT_OF_INPUT
            "right_of_input" -> LayoutSlot.RIGHT_OF_INPUT
            "on_input" -> LayoutSlot.ON_INPUT
            "paper_margin" -> LayoutSlot.PAPER_MARGIN
            "top_left" -> LayoutSlot.TOP_LEFT
            "top_right" -> LayoutSlot.TOP_RIGHT
            "bottom_left" -> LayoutSlot.BOTTOM_LEFT
            "bottom_right" -> LayoutSlot.BOTTOM_RIGHT
            else -> LayoutSlot.CENTER
        }
    }

    private fun normalizedDirectionForArrow(direction: String): String {
        return when (direction) {
            "left", "right", "top", "bottom", "top_left", "top_right", "bottom_left", "bottom_right" -> direction
            else -> "left"
        }
    }

    private fun normalizedSizeLabel(size: String): String {
        return when (size) {
            "small", "medium", "large" -> size
            else -> "medium"
        }
    }

    private fun maxWidthForSlot(slot: LayoutSlot, style: String): Float {
        val maxByCanvas = when (slot) {
            LayoutSlot.BELOW_INPUT, LayoutSlot.ABOVE_INPUT -> width * 0.42f
            LayoutSlot.LEFT_OF_INPUT, LayoutSlot.RIGHT_OF_INPUT -> width * 0.26f
            else -> width * 0.22f
        }
        val clamped = max(min(maxByCanvas, width - 120f), 110f)
        return if (style == "annotation") min(clamped, 210f) else max(clamped, 160f)
    }

    private fun circleSizeFor(size: String, inputBounds: RectF): PointF {
        val padX = when (size) {
            "small" -> 14f
            "large" -> 26f
            else -> 20f
        }
        val padY = when (size) {
            "small" -> 10f
            "large" -> 20f
            else -> 14f
        }
        return PointF(
            max(inputBounds.width() * 0.55f + padX, 40f),
            max(inputBounds.height() * 0.55f + padY, 26f),
        )
    }

    private fun underlineWidthFor(inputBounds: RectF): Float {
        return clamp(inputBounds.width() + 26f, 96f, min(width * 0.52f, 240f))
    }

    private fun measureBounds(element: CanvasElement): RectF {
        return when (element) {
            is DotElement -> RectF(
                element.x - element.radius,
                element.y - element.radius,
                element.x + element.radius,
                element.y + element.radius,
            )
            is TextElement -> measureTextBounds(element)
            is CircleElement -> RectF(
                element.centerX - element.radiusX - 6f,
                element.centerY - element.radiusY - 6f,
                element.centerX + element.radiusX + 6f,
                element.centerY + element.radiusY + 6f,
            )
            is ArrowElement -> {
                val controlX = (element.startX + element.endX) / 2f + element.curve
                val controlY = (element.startY + element.endY) / 2f - element.curve * 0.4f
                RectF(
                    min(min(element.startX, element.endX), controlX) - 14f,
                    min(min(element.startY, element.endY), controlY) - 14f,
                    max(max(element.startX, element.endX), controlX) + 14f,
                    max(max(element.startY, element.endY), controlY) + 14f,
                )
            }
            is UnderlineElement -> RectF(
                element.startX - 6f,
                element.y - 16f,
                element.startX + element.width + 6f,
                element.y + 16f,
            )
            is PathElement -> RectF().also { rect ->
                element.path.computeBounds(rect, true)
                rect.inset(-element.strokeWidth * 1.5f, -element.strokeWidth * 1.5f)
            }
            is BubbleElement -> RectF(element.rect).apply { inset(-8f, -8f) }
            is BurstElement -> RectF(
                element.x - element.radius - 6f,
                element.y - element.radius - 6f,
                element.x + element.radius + 6f,
                element.y + element.radius + 6f,
            )
        }
    }

    private fun measureTextBounds(element: TextElement): RectF {
        configureTextPaint(element.style, element.textSize)
        val lines = wrapTextLines(element.content, element.maxWidth)
        val maxLineWidth = lines.maxOfOrNull { textPaint.measureText(it) } ?: 0f
        val lineHeight = lineHeightForStyle(element.style)
        val height = max(lineHeight * lines.size, textPaint.textSize)
        val ascentPad = when (element.style) {
            TextStyle.ANNOTATION -> 26f
            TextStyle.QUESTION -> 30f
            TextStyle.ANSWER -> 34f
        }
        return RectF(
            element.x - 8f,
            element.y - ascentPad,
            element.x + maxLineWidth + 12f,
            element.y + height * 0.82f,
        )
    }

    private fun configureTextPaint(style: TextStyle, textSize: Float, content: String = "") {
        val hasCjk = content.any { it.code > 127 }
        textPaint.textSize = when (style) {
            TextStyle.ANSWER -> textSize
            TextStyle.ANNOTATION -> min(textSize, 39f)
            TextStyle.QUESTION -> textSize
        }
        textPaint.typeface = when {
            hasCjk && style == TextStyle.ANNOTATION -> annotationChineseTypeface
            hasCjk -> answerChineseTypeface
            style == TextStyle.ANNOTATION -> annotationLatinTypeface
            else -> answerLatinTypeface
        }
        textPaint.color = when (style) {
            TextStyle.ANNOTATION -> 0xFF6E4D3B.toInt()
            TextStyle.QUESTION -> 0xFF4A362D.toInt()
            TextStyle.ANSWER -> 0xFF35251F.toInt()
        }
    }

    private fun wrapTextLines(text: String, maxWidth: Float): List<String> {
        val lines = mutableListOf<String>()
        for (paragraph in text.split("\n")) {
            var line = ""
            for (char in paragraph) {
                val testLine = line + char
                if (textPaint.measureText(testLine) > maxWidth && line.isNotEmpty()) {
                    lines.add(line)
                    line = char.toString()
                } else {
                    line = testLine
                }
            }
            if (line.isNotEmpty()) {
                lines.add(line)
            }
        }
        return if (lines.isEmpty()) listOf("") else lines
    }

    private fun controlAvoidRect(): RectF {
        return RectF(
            max(width - 172f, width * 0.7f),
            max(height - 136f, height * 0.72f),
            width.toFloat(),
            height.toFloat(),
        )
    }

    private fun isInSafeArea(rect: RectF): Boolean {
        return rect.left >= 18f &&
            rect.top >= 22f &&
            rect.right <= width - 18f &&
            rect.bottom <= height - 26f
    }

    private fun expandedRect(rect: RectF, dx: Float, dy: Float): RectF {
        return RectF(rect.left - dx, rect.top - dy, rect.right + dx, rect.bottom + dy)
    }

    private fun pointForAnchor(anchor: String, target: String = "input", seed: Int = 0): PointF {
        if (target == "input") {
            val bounds = layoutInputBounds()
            val gap = 42f
            return when (anchor) {
                "above_input" -> PointF(bounds.centerX(), bounds.top - gap)
                "below_input" -> PointF(bounds.centerX(), bounds.bottom + gap)
                "left_of_input" -> PointF(bounds.left - gap, bounds.centerY())
                "right_of_input" -> PointF(bounds.right + gap, bounds.centerY())
                "on_input" -> PointF(bounds.centerX(), bounds.centerY())
                "paper_margin" -> PointF(width * 0.18f + stableOffset(seed, 1, 22f), height * 0.18f)
                else -> pointForPaperAnchor(anchor)
            }.let { clampPoint(it) }
        }
        return clampPoint(pointForPaperAnchor(anchor))
    }

    private fun pointForPaperAnchor(anchor: String): PointF {
        val safeWidth = max(width.toFloat(), 320f)
        val safeHeight = max(height.toFloat(), 320f)
        val left = safeWidth * 0.18f
        val right = safeWidth * 0.68f
        val top = safeHeight * 0.18f
        val bottom = safeHeight * 0.64f
        return when (anchor) {
            "top_left" -> PointF(left, top)
            "top_right" -> PointF(right, top)
            "bottom_left" -> PointF(left, bottom)
            "bottom_right" -> PointF(right, bottom)
            else -> PointF(safeWidth * 0.5f, safeHeight * 0.38f)
        }
    }

    private fun pointForDirection(direction: String, target: String = "input", seed: Int = 0): PointF {
        if (direction in setOf("above_input", "below_input", "left_of_input", "right_of_input", "on_input", "paper_margin")) {
            return pointForAnchor(direction, target, seed)
        }
        val safeWidth = max(width.toFloat(), 320f)
        val safeHeight = max(height.toFloat(), 320f)
        return when (direction) {
            "left" -> PointF(safeWidth * 0.12f, safeHeight * 0.42f)
            "right" -> PointF(safeWidth * 0.82f, safeHeight * 0.42f)
            "top" -> PointF(safeWidth * 0.5f, safeHeight * 0.16f)
            "bottom" -> PointF(safeWidth * 0.5f, safeHeight * 0.72f)
            else -> pointForAnchor(direction, target, seed)
        }.let { clampPoint(it) }
    }

    private fun textSizeFor(size: String, style: String): Float {
        if (style == "annotation") {
            return when (size) {
                "small" -> 28f
                "large" -> 40f
                else -> 34f
            }
        }
        return when (size) {
            "small" -> 34f
            "large" -> 56f
            else -> 46f
        }
    }

    private fun doodleSizeFor(size: String): PointF {
        return when (size) {
            "small" -> PointF(44f, 28f)
            "large" -> PointF(112f, 70f)
            else -> PointF(76f, 48f)
        }
    }

    private fun doodleScalarFor(size: String): Float {
        return when (size) {
            "small" -> 54f
            "large" -> 120f
            else -> 82f
        }
    }

    private fun computeInkBounds(): RectF? {
        val points = buildList {
            for (stroke in strokes) addAll(stroke)
            currentStroke?.let { addAll(it) }
        }
        if (points.isEmpty()) return null
        var left = points.first().x
        var top = points.first().y
        var right = points.first().x
        var bottom = points.first().y
        for (point in points) {
            left = min(left, point.x)
            top = min(top, point.y)
            right = max(right, point.x)
            bottom = max(bottom, point.y)
        }
        return RectF(
            clamp(left - 18f, 18f, width - 18f),
            clamp(top - 18f, 18f, height - 18f),
            clamp(right + 18f, 18f, width - 18f),
            clamp(bottom + 18f, 18f, height - 18f),
        )
    }

    private fun layoutInputBounds(): RectF {
        val fallbackWidth = max(width * 0.24f, 120f)
        val fallbackHeight = max(height * 0.12f, 80f)
        val fallback = RectF(
            width * 0.5f - fallbackWidth * 0.5f,
            height * 0.36f - fallbackHeight * 0.5f,
            width * 0.5f + fallbackWidth * 0.5f,
            height * 0.36f + fallbackHeight * 0.5f,
        )
        val bounds = RectF(lastInputBounds ?: fallback)
        if (bounds.width() < 48f) {
            bounds.inset(-(48f - bounds.width()) * 0.5f, 0f)
        }
        if (bounds.height() < 44f) {
            bounds.inset(0f, -(44f - bounds.height()) * 0.5f)
        }
        bounds.offsetTo(
            clamp(bounds.left, 36f, width - bounds.width() - 36f),
            clamp(bounds.top, 36f, height - bounds.height() - 96f),
        )
        return bounds
    }

    private fun clampPoint(point: PointF): PointF {
        val avoidRight = 132f
        val avoidBottom = 108f
        return PointF(
            clamp(point.x, 28f, max(28f, width - avoidRight)),
            clamp(point.y, 34f, max(34f, height - avoidBottom)),
        )
    }

    private fun roundedWobbleRect(rect: RectF, radius: Float, seed: Int): Path {
        val path = Path()
        val stepsPerSide = 8
        fun addPoint(x: Float, y: Float, index: Int) {
            val px = x + stableOffset(seed, index, 2.2f)
            val py = y + stableOffset(seed, index + 41, 2.2f)
            if (path.isEmpty) path.moveTo(px, py) else path.lineTo(px, py)
        }
        var index = 0
        for (i in 0..stepsPerSide) addPoint(rect.left + radius + (rect.width() - radius * 2f) * i / stepsPerSide, rect.top, index++)
        for (i in 0..stepsPerSide) addPoint(rect.right, rect.top + radius + (rect.height() - radius * 2f) * i / stepsPerSide, index++)
        for (i in 0..stepsPerSide) addPoint(rect.right - radius - (rect.width() - radius * 2f) * i / stepsPerSide, rect.bottom, index++)
        for (i in 0..stepsPerSide) addPoint(rect.left, rect.bottom - radius - (rect.height() - radius * 2f) * i / stepsPerSide, index++)
        path.close()
        return path
    }

    private fun stableSeed(index: Int, command: CanvasCommand): Int {
        return 31 * (index + 1) + command.toString().hashCode()
    }

    private fun stableUnit(seed: Int): Float {
        val value = kotlin.math.abs((seed * 1103515245 + 12345) xor (seed ushr 16))
        return (value % 10_000) / 10_000f
    }

    private fun stableOffset(seed: Int, salt: Int, range: Float): Float {
        return (stableUnit(seed + salt * 9973) - 0.5f) * range
    }

    private fun randomOffset(range: Float): Float = (Random.nextFloat() - 0.5f) * range

    private fun clamp(value: Float, minValue: Float, maxValue: Float): Float {
        if (maxValue < minValue) return minValue
        return max(minValue, min(value, maxValue))
    }

    private fun loadTypeface(assetPath: String): Typeface? {
        return try {
            Typeface.createFromAsset(context.assets, assetPath)
        } catch (_: Exception) {
            null
        }
    }
}

private sealed interface CanvasElement

private enum class LayoutSlot {
    ON_INPUT,
    ABOVE_INPUT,
    BELOW_INPUT,
    LEFT_OF_INPUT,
    RIGHT_OF_INPUT,
    PAPER_MARGIN,
    TOP_LEFT,
    TOP_RIGHT,
    BOTTOM_LEFT,
    BOTTOM_RIGHT,
    CENTER,
}

private data class PlacementCandidate(
    val slot: LayoutSlot,
    val size: String,
    val offsetX: Float,
    val offsetY: Float,
)

private data class DotElement(
    val x: Float,
    val y: Float,
    val radius: Float,
    val alpha: Float,
) : CanvasElement

private data class TextElement(
    val content: String,
    val x: Float,
    val y: Float,
    val style: TextStyle,
    val rotate: Float,
    val maxWidth: Float,
    val textSize: Float,
) : CanvasElement

private data class CircleElement(
    val centerX: Float,
    val centerY: Float,
    val radiusX: Float,
    val radiusY: Float,
    val rotate: Float,
    val wobbleSeed: Float,
) : CanvasElement

private data class ArrowElement(
    val startX: Float,
    val startY: Float,
    val endX: Float,
    val endY: Float,
    val curve: Float,
) : CanvasElement

private data class UnderlineElement(
    val startX: Float,
    val y: Float,
    val width: Float,
    val wave: Float,
) : CanvasElement

private data class PathElement(
    val path: Path,
    val strokeWidth: Float,
    val alpha: Int,
) : CanvasElement

private data class BubbleElement(
    val rect: RectF,
    val rotate: Float,
    val seed: Int,
) : CanvasElement

private data class BurstElement(
    val x: Float,
    val y: Float,
    val radius: Float,
    val rotate: Float,
    val seed: Int,
) : CanvasElement

private enum class TextStyle {
    QUESTION,
    ANSWER,
    ANNOTATION,
}

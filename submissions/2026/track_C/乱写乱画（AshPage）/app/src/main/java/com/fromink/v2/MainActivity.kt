package com.fromink.v2

import android.Manifest
import android.app.Activity
import android.content.res.ColorStateList
import android.content.pm.PackageManager
import android.os.Bundle
import android.text.TextUtils
import android.util.Log
import android.view.Gravity
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

private const val MODEL_FILENAME = "model.litertlm"
private const val AUTO_SUBMIT_DELAY_MS = 3000L
private const val PAPER_MARGIN_DP = 36
private const val PAPER_CONTENT_INSET_DP = 24
private const val CONTROL_INSET_DP = 12
private const val RECORD_AUDIO_PERMISSION_REQUEST = 1001
private const val OVERLAY_ELEVATION_DP = 24
private const val TAG = "FromInkMain"

class MainActivity : Activity() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    private lateinit var statusView: TextView
    private lateinit var inkCanvasView: InkCanvasView
    private lateinit var undoButton: ImageButton
    private lateinit var clearButton: ImageButton
    private lateinit var askButton: ImageButton
    private lateinit var micButton: ImageButton

    private var inference: GemmaInference? = null
    private var analyzeJob: Job? = null
    private var autoSubmitJob: Job? = null
    private var audioJob: Job? = null
    private var audioRecorder: AudioRecorder? = null
    private var isRecordingAudio = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(createContentView())
        setControlsEnabled(false)

        undoButton.setOnClickListener {
            clearAutoSubmit()
            inkCanvasView.undo()
            if (inkCanvasView.hasInk()) {
                scheduleAutoSubmit()
            } else {
                statusView.text = "Ready"
            }
        }
        clearButton.setOnClickListener {
            clearAutoSubmit()
            inkCanvasView.clearAll()
            statusView.text = "Ready"
        }
        askButton.setOnClickListener {
            clearAutoSubmit()
            analyzeInk()
        }
        micButton.setOnClickListener { toggleAudioRecording() }

        initializeInference()
    }

    private fun createContentView(): FrameLayout {
        val root = FrameLayout(this).apply {
            setBackgroundColor(0xFF110D08.toInt())
        }

        inkCanvasView = InkCanvasView(this).apply {
            elevation = dp(16).toFloat()
            onStrokeStarted = {
                clearAutoSubmit()
                statusView.text = "Ready"
            }
            onStrokeEnded = {
                scheduleAutoSubmit()
            }
        }
        root.addView(
            inkCanvasView,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT,
            ).apply {
                setMargins(
                    dp(PAPER_MARGIN_DP),
                    dp(PAPER_MARGIN_DP),
                    dp(PAPER_MARGIN_DP),
                    dp(PAPER_MARGIN_DP),
                )
            },
        )

        val labelView = TextView(this).apply {
            text = "AshPage"
            textSize = 12f
            letterSpacing = 0.1f
            setTextColor(0x8CB44637.toInt())
            setAllCaps(true)
            elevation = dp(OVERLAY_ELEVATION_DP).toFloat()
        }
        root.addView(
            labelView,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.TOP or Gravity.START,
            ).apply {
                topMargin = dp(PAPER_MARGIN_DP + PAPER_CONTENT_INSET_DP)
                leftMargin = dp(PAPER_MARGIN_DP + PAPER_CONTENT_INSET_DP)
            },
        )

        statusView = TextView(this).apply {
            text = "Loading model..."
            textSize = 12f
            gravity = Gravity.END
            maxLines = 2
            ellipsize = TextUtils.TruncateAt.END
            setTextColor(0x99796754.toInt())
            elevation = dp(OVERLAY_ELEVATION_DP).toFloat()
        }
        root.addView(
            statusView,
            FrameLayout.LayoutParams(
                dp(230),
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.TOP or Gravity.END,
            ).apply {
                topMargin = dp(PAPER_MARGIN_DP + PAPER_CONTENT_INSET_DP)
                rightMargin = dp(PAPER_MARGIN_DP + PAPER_CONTENT_INSET_DP)
            },
        )

        val controls = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            elevation = dp(OVERLAY_ELEVATION_DP).toFloat()
        }
        undoButton = makeIconButton(R.drawable.ic_undo, "Undo")
        clearButton = makeIconButton(R.drawable.ic_clear, "Clear")
        askButton = makeIconButton(R.drawable.ic_send, "Ask")
        micButton = makeIconButton(R.drawable.ic_mic, "Record audio")
        controls.addView(undoButton)
        controls.addView(clearButton)
        controls.addView(askButton)
        controls.addView(micButton)
        root.addView(
            controls,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM or Gravity.END,
            ).apply {
                rightMargin = dp(PAPER_MARGIN_DP + CONTROL_INSET_DP)
                bottomMargin = dp(PAPER_MARGIN_DP + CONTROL_INSET_DP)
            },
        )

        return root
    }

    private fun makeIconButton(iconResId: Int, description: String): ImageButton {
        return ImageButton(this).apply {
            setImageResource(iconResId)
            contentDescription = description
            background = null
            imageTintList = ColorStateList.valueOf(0xFF796754.toInt())
            alpha = 0.42f
            scaleType = ImageView.ScaleType.CENTER
            setPadding(dp(8), dp(8), dp(8), dp(8))
            layoutParams = LinearLayout.LayoutParams(dp(42), dp(42))
        }
    }

    private fun initializeInference() {
        scope.launch {
            val modelFile = getModelFile()
            if (!modelFile.exists()) {
                statusView.text = "Model not found"
                inkCanvasView.showAnnotation("Place model.litertlm in the app files directory.")
                setControlsEnabled(false)
                return@launch
            }

            try {
                val initialized = withContext(Dispatchers.IO) {
                    GemmaInference(
                        context = applicationContext,
                        modelPath = modelFile.absolutePath,
                        cacheDir = cacheDir.absolutePath,
                    ).also { it.initialize() }
                }
                inference = initialized
                statusView.text = "Ready: ${modelFile.name}"
                setControlsEnabled(true)
            } catch (e: Exception) {
                statusView.text = "Failed to load model"
                inkCanvasView.showAnnotation(e.message ?: "Failed to load model.")
                setControlsEnabled(false)
            }
        }
    }

    private fun analyzeInk() {
        clearAutoSubmit()
        if (analyzeJob?.isActive == true || isRecordingAudio) {
            return
        }
        if (!inkCanvasView.hasInk()) {
            statusView.text = "Write something first."
            inkCanvasView.showAnnotation("Write something first.")
            return
        }

        val activeInference = inference
        if (activeInference == null) {
            statusView.text = "Model is not ready."
            return
        }

        analyzeJob = scope.launch {
            setControlsEnabled(false)
            statusView.text = "Waiting..."

            try {
                val imageBytes = inkCanvasView.toPngBytes()
                inkCanvasView.showWaitingWave()
                val result = withContext(Dispatchers.IO) {
                    activeInference.analyze(imageBytes)
                }
                val commands = result.visibleCommands()
                debugLog("image result: action=${result.action}, commands=${commands.size}, raw=${result.rawText}")
                if (result.action == "stay_silent" || commands.isEmpty()) {
                    inkCanvasView.showSilentDot()
                } else {
                    inkCanvasView.showCanvasCommands(commands)
                }
                statusView.text = buildStatusText(result.displayText, result.skillUsage)
            } catch (e: Exception) {
                statusView.text = "Inference failed"
                inkCanvasView.showAnnotation(e.message ?: "Inference failed.")
            } finally {
                setControlsEnabled(inference != null)
            }
        }
    }

    private fun toggleAudioRecording() {
        if (isRecordingAudio) {
            stopAudioRecording()
            return
        }
        startAudioRecording()
    }

    private fun startAudioRecording() {
        clearAutoSubmit()
        if (analyzeJob?.isActive == true) return
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), RECORD_AUDIO_PERMISSION_REQUEST)
            return
        }

        val activeInference = inference
        if (activeInference == null) {
            statusView.text = "Model is not ready."
            return
        }

        val recorder = AudioRecorder()
        audioRecorder = recorder
        isRecordingAudio = true
        setRecordingUi(true)
        inkCanvasView.showAnnotation("Recording...")
        statusView.text = "Recording..."

        audioJob = scope.launch {
            try {
                val audioBytes = withContext(Dispatchers.IO) {
                    recorder.recordWavBytes()
                }
                if (audioBytes.size <= 44) {
                    statusView.text = "Recording was empty"
                    inkCanvasView.showAnnotation("Recording was empty.")
                    return@launch
                }

                setControlsEnabled(false)
                statusView.text = "Waiting..."
                inkCanvasView.showWaitingWave()
                val result = withContext(Dispatchers.IO) {
                    activeInference.analyzeAudio(audioBytes)
                }
                val commands = result.visibleCommands()
                debugLog("audio result: action=${result.action}, commands=${commands.size}, raw=${result.rawText}")
                if (result.action == "stay_silent" || commands.isEmpty()) {
                    inkCanvasView.showSilentDot()
                } else {
                    inkCanvasView.showCanvasCommands(commands)
                }
                statusView.text = buildStatusText(result.displayText, result.skillUsage)
            } catch (e: Exception) {
                statusView.text = "Audio failed"
                inkCanvasView.showAnnotation(e.message ?: "Audio failed.")
            } finally {
                audioRecorder = null
                isRecordingAudio = false
                setRecordingUi(false)
                setControlsEnabled(inference != null)
            }
        }
    }

    private fun stopAudioRecording() {
        if (!isRecordingAudio) return
        statusView.text = "Waiting..."
        inkCanvasView.showWaitingWave()
        audioRecorder?.stop()
    }

    private fun scheduleAutoSubmit() {
        clearAutoSubmit()
        if (!inkCanvasView.hasInk() || inference == null || analyzeJob?.isActive == true) {
            return
        }

        statusView.text = "Auto submit in 3s"
        autoSubmitJob = scope.launch {
            delay(AUTO_SUBMIT_DELAY_MS)
            if (inkCanvasView.hasInk() && inference != null && analyzeJob?.isActive != true) {
                analyzeInk()
            }
        }
    }

    private fun clearAutoSubmit() {
        autoSubmitJob?.cancel()
        autoSubmitJob = null
    }

    private fun getModelFile(): File {
        val dir = getExternalFilesDir(null) ?: filesDir
        return File(dir, MODEL_FILENAME)
    }

    private fun setControlsEnabled(enabled: Boolean) {
        inkCanvasView.isEnabled = enabled
        val controls = listOf(undoButton, clearButton, askButton, micButton)
        for (button in controls) {
            button.isEnabled = enabled
            button.alpha = if (enabled) 0.42f else 0.15f
        }
    }

    private fun setRecordingUi(recording: Boolean) {
        inkCanvasView.isEnabled = !recording
        undoButton.isEnabled = !recording
        clearButton.isEnabled = !recording
        askButton.isEnabled = !recording
        micButton.isEnabled = true
        micButton.alpha = if (recording) 0.95f else 0.42f
        micButton.imageTintList = ColorStateList.valueOf(
            if (recording) 0xFF8A4B2F.toInt() else 0xFF796754.toInt(),
        )
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != RECORD_AUDIO_PERMISSION_REQUEST) return
        if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            startAudioRecording()
        } else {
            statusView.text = "Microphone permission denied"
            inkCanvasView.showAnnotation("Microphone permission denied.")
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun debugLog(message: String) {
        if (BuildConfig.DEBUG) {
            Log.d(TAG, message)
        }
    }

    private fun buildStatusText(recognizedText: String, skillUsage: SkillUsageStatus): String {
        val base = recognizedText.ifBlank { "Ready" }
        val skillLabel = when {
            skillUsage.status == "ok" && !skillUsage.name.isNullOrBlank() -> "skill: ${skillUsage.name}"
            skillUsage.called -> "skill: ${skillUsage.status}"
            else -> "skill: none"
        }
        return "$base  |  $skillLabel"
    }

    override fun onDestroy() {
        clearAutoSubmit()
        audioRecorder?.stop()
        audioJob?.cancel()
        analyzeJob?.cancel()
        inference?.close()
        scope.cancel()
        super.onDestroy()
    }
}

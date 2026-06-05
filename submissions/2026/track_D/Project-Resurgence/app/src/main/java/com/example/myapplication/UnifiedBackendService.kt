package com.example.myapplication

import android.app.Service
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Binder
import android.os.IBinder
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Conversation
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.SamplerConfig
import fi.iki.elonen.NanoHTTPD
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File

class UnifiedBackendService : Service() {

    private val binder = LocalBinder()
    private val inferenceAdapter by lazy { UnifiedGemmaInferenceAdapter(this) }
    private val apiServer by lazy { UnifiedApiServer(inferenceAdapter) }

    inner class LocalBinder : Binder() {
        fun getService(): UnifiedBackendService = this@UnifiedBackendService
    }

    override fun onCreate() {
        super.onCreate()
        apiServer.startServer()
    }

    override fun onDestroy() {
        apiServer.stop()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder = binder
}

private class UnifiedApiServer(
    private val adapter: UnifiedGemmaInferenceAdapter,
    port: Int = 8080
) : NanoHTTPD(port) {

    fun startServer() {
        start(SOCKET_READ_TIMEOUT, false)
    }

    override fun serve(session: IHTTPSession): Response = try {
        when {
            session.method == Method.GET && session.uri == "/health" -> json(Response.Status.OK, JSONObject().put("ok", true))
            session.method == Method.POST && session.uri == "/api/gemma4e2b/chat" -> {
                val body = readBody(session)
                val json = JSONObject(body.ifBlank { "{}" })
                val text = json.optString("text")
                val image = decodeBitmap(json.optString("imageBase64", ""))
                val reply = runBlocking { adapter.startSurvivalInferenceText(image, text) }
                json(Response.Status.OK, JSONObject().put("reply", reply))
            }
            session.method == Method.POST && session.uri == "/api/gemma4e2b/analyze" -> {
                val body = readBody(session)
                val json = JSONObject(body.ifBlank { "{}" })
                val text = json.optString("text")
                val image = decodeBitmap(json.optString("imageBase64", ""))
                val summary = adapter.compressScene(image, text)
                json(Response.Status.OK, JSONObject().put("summary", summary))
            }
            session.method == Method.POST && session.uri == "/api/gemma4e2b/arbitrate" -> {
                val body = readBody(session)
                val json = JSONObject(body.ifBlank { "{}" })
                val reports = json.optJSONArray("reports")?.let { arr ->
                    buildList { for (i in 0 until arr.length()) add(arr.optString(i)) }
                }.orEmpty()
                val trusted = runBlocking { adapter.arbitrateRumor(reports) }
                json(Response.Status.OK, JSONObject().put("trusted", trusted))
            }
            else -> json(Response.Status.NOT_FOUND, JSONObject().put("error", "not_found"))
        }
    } catch (e: Exception) {
        json(Response.Status.INTERNAL_ERROR, JSONObject().put("error", e.message ?: "internal_error"))
    }

    private fun readBody(session: IHTTPSession): String {
        val files = hashMapOf<String, String>()
        session.parseBody(files)
        return files["postData"] ?: ""
    }

    private fun decodeBitmap(base64: String): Bitmap? {
        if (base64.isBlank()) return null
        val bytes = android.util.Base64.decode(base64, android.util.Base64.DEFAULT)
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
    }

    private fun json(status: Response.Status, obj: JSONObject): Response =
        newFixedLengthResponse(status, "application/json", obj.toString())
}

private class UnifiedGemmaInferenceAdapter(
    private val context: Service,
    private val backend: Backend = Backend.CPU()
) {
    private var engine: Engine? = null

    @Synchronized
    private fun getEngine(): Engine {
        val existing = engine
        if (existing != null) return existing

        val created = Engine(
            EngineConfig(
                modelPath = resolveModelPath(),
                backend = backend,
                cacheDir = context.cacheDir.absolutePath
            )
        )
        created.initialize()
        engine = created
        return created
    }

    private fun createConversation(): Conversation =
        getEngine().createConversation(
            ConversationConfig(
                samplerConfig = SamplerConfig(
                    topK = 40,
                    topP = 0.95,
                    temperature = 0.7
                )
            )
        )

    fun compressScene(bitmap: Bitmap?, textDescription: String): String {
        val prompt = "请将以下场景压缩成极简键值对，不超过30字节：${if (bitmap != null) "[有图片] " else ""}$textDescription"
        return try {
            createConversation().use { conversation ->
                conversation.sendMessage(prompt).toString().take(64)
            }
        } catch (_: Throwable) {
            "I0|T0"
        }
    }

    fun startSurvivalInferenceText(bitmap: Bitmap?, userQuestion: String): String = runBlocking {
        val prompt = buildString {
            if (bitmap != null) append("请结合图片回答。")
            append(userQuestion)
        }
        try {
            createConversation().use { conversation ->
                conversation.sendMessage(prompt).toString()
            }
        } catch (_: Throwable) {
            "模型未返回有效内容"
        }
    }

    suspend fun arbitrateRumor(reports: List<String>): Boolean = withContext(Dispatchers.Default) {
        val prompt = buildString {
            appendLine("判断以下报告是否为谣言，仅回答 true 或 false。")
            for (index in reports.indices) appendLine("${index + 1}. ${reports[index]}")
            append("如果存在明显夸大、重复、无法核实内容则认为是谣言。")
        }
        try {
            createConversation().use { conversation ->
                val reply = conversation.sendMessage(prompt).toString().lowercase()
                reply.contains("true") || reply.contains("是")
            }
        } catch (_: Throwable) {
            reports.isNotEmpty()
        }
    }

    private fun resolveModelPath(): String {
        val downloadDir = File("/sdcard/Download")
        val preferred = File(downloadDir, MODEL_FILE_NAME)
        if (preferred.exists() && preferred.length() > 0L) return preferred.absolutePath

        val alt1 = File(downloadDir, "gemma-4-E2B-it.litertlm")
        if (alt1.exists() && alt1.length() > 0L) return alt1.absolutePath

        val alt2 = File(downloadDir, "gemma4.litertlm")
        if (alt2.exists() && alt2.length() > 0L) return alt2.absolutePath

        return preferred.absolutePath
    }

    private companion object {
        const val MODEL_FILE_NAME = "gemma4e2b.bin"
    }
}

package com.example.myapplication

import android.graphics.Bitmap
import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit

object BackendApiClient {
    var baseUrlOverride: String? = null
    private const val BASE_URL = "http://10.0.2.2:8080"
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    suspend fun chat(text: String, image: Bitmap? = null): String = withContext(Dispatchers.IO) {
        val payload = JSONObject().apply {
            put("text", text)
            image?.let { put("imageBase64", bitmapToBase64(it)) }
        }
        val request = Request.Builder()
            .url("$BASE_URL/api/gemma4e2b/chat")
            .post(payload.toString().toRequestBody(jsonMediaType))
            .build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("HTTP ${response.code}")
            JSONObject(response.body?.string().orEmpty()).optString("reply")
        }
    }

    suspend fun analyze(text: String, image: Bitmap? = null): String = withContext(Dispatchers.IO) {
        val payload = JSONObject().apply {
            put("text", text)
            image?.let { put("imageBase64", bitmapToBase64(it)) }
        }
        val request = Request.Builder()
            .url("$BASE_URL/api/gemma4e2b/analyze")
            .post(payload.toString().toRequestBody(jsonMediaType))
            .build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("HTTP ${response.code}")
            JSONObject(response.body?.string().orEmpty()).optString("summary")
        }
    }

    suspend fun arbitrate(reports: List<String>): Boolean = withContext(Dispatchers.IO) {
        val payload = JSONObject().apply {
            put("reports", JSONArray(reports))
        }
        val request = Request.Builder()
            .url("$BASE_URL/api/gemma4e2b/arbitrate")
            .post(payload.toString().toRequestBody(jsonMediaType))
            .build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("HTTP ${response.code}")
            JSONObject(response.body?.string().orEmpty()).optBoolean("trusted")
        }
    }

    suspend fun uploadPhoto(bitmap: Bitmap, language: Language): Boolean = withContext(Dispatchers.IO) {
        runCatching {
            analyze("upload", bitmap)
            true
        }.getOrDefault(false)
    }

    private fun bitmapToBase64(bitmap: Bitmap): String {
        val stream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, 85, stream)
        return Base64.encodeToString(stream.toByteArray(), Base64.NO_WRAP)
    }
}

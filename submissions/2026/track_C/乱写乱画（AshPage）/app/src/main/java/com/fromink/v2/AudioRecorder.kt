package com.fromink.v2

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

private const val AUDIO_SAMPLE_RATE = 16_000
private const val AUDIO_CHANNEL_COUNT = 1
private const val AUDIO_BITS_PER_SAMPLE = 16

class AudioRecorder {
    @Volatile
    private var isRecording = false
    private var audioRecord: AudioRecord? = null

    @SuppressLint("MissingPermission")
    fun recordWavBytes(): ByteArray {
        val minBufferSize = AudioRecord.getMinBufferSize(
            AUDIO_SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        val bufferSize = maxOf(minBufferSize, AUDIO_SAMPLE_RATE / 2)
        val recorder = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            AUDIO_SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize,
        )
        val pcmBytes = ByteArrayOutputStream()
        val buffer = ByteArray(bufferSize)

        audioRecord = recorder
        isRecording = true
        recorder.startRecording()
        try {
            while (isRecording) {
                val read = recorder.read(buffer, 0, buffer.size)
                if (read > 0) {
                    pcmBytes.write(buffer, 0, read)
                }
            }
        } finally {
            try {
                recorder.stop()
            } catch (_: Exception) {
            }
            recorder.release()
            audioRecord = null
        }

        return buildWavBytes(pcmBytes.toByteArray())
    }

    fun stop() {
        isRecording = false
        try {
            audioRecord?.stop()
        } catch (_: Exception) {
        }
    }

    private fun buildWavBytes(pcmBytes: ByteArray): ByteArray {
        val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        val byteRate = AUDIO_SAMPLE_RATE * AUDIO_CHANNEL_COUNT * AUDIO_BITS_PER_SAMPLE / 8
        val blockAlign = AUDIO_CHANNEL_COUNT * AUDIO_BITS_PER_SAMPLE / 8
        val dataSize = pcmBytes.size
        val riffSize = 36 + dataSize

        header.put("RIFF".toByteArray(Charsets.US_ASCII))
        header.putInt(riffSize)
        header.put("WAVE".toByteArray(Charsets.US_ASCII))
        header.put("fmt ".toByteArray(Charsets.US_ASCII))
        header.putInt(16)
        header.putShort(1)
        header.putShort(AUDIO_CHANNEL_COUNT.toShort())
        header.putInt(AUDIO_SAMPLE_RATE)
        header.putInt(byteRate)
        header.putShort(blockAlign.toShort())
        header.putShort(AUDIO_BITS_PER_SAMPLE.toShort())
        header.put("data".toByteArray(Charsets.US_ASCII))
        header.putInt(dataSize)

        return ByteArrayOutputStream().use { output ->
            output.write(header.array())
            output.write(pcmBytes)
            output.toByteArray()
        }
    }
}

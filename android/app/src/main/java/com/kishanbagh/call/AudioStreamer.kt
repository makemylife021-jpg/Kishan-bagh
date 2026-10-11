package com.kishanbagh.call

import android.annotation.SuppressLint
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import java.io.InputStream
import java.io.OutputStream
import kotlin.concurrent.thread

/**
 * Sends microphone audio into an OutputStream and plays audio read from an InputStream.
 * Raw 16 kHz mono PCM (about 256 kbit/s): simple and low-latency, well within
 * what Bluetooth and Wi-Fi Direct can carry.
 */
class AudioStreamer {
    companion object {
        const val SAMPLE_RATE = 16_000
    }

    @Volatile var muted = false
    @Volatile private var running = false
    private var recordThread: Thread? = null
    private var playThread: Thread? = null

    @SuppressLint("MissingPermission") // RECORD_AUDIO is checked before a call starts.
    fun startSending(out: OutputStream) {
        running = true
        recordThread = thread(name = "mic-sender") {
            val minBuf = AudioRecord.getMinBufferSize(
                SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
            )
            val recorder = AudioRecord(
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
                minBuf * 2
            )
            val echo = if (AcousticEchoCanceler.isAvailable())
                AcousticEchoCanceler.create(recorder.audioSessionId)?.apply { enabled = true } else null
            val noise = if (NoiseSuppressor.isAvailable())
                NoiseSuppressor.create(recorder.audioSessionId)?.apply { enabled = true } else null

            // 20 ms of audio per chunk.
            val buffer = ByteArray(SAMPLE_RATE / 50 * 2)
            try {
                recorder.startRecording()
                while (running) {
                    val n = recorder.read(buffer, 0, buffer.size)
                    if (n <= 0) continue
                    if (muted) buffer.fill(0, 0, n)
                    out.write(buffer, 0, n)
                    out.flush()
                }
            } catch (_: Exception) {
                // Stream closed: the call ended.
            } finally {
                runCatching { recorder.stop() }
                recorder.release()
                echo?.release()
                noise?.release()
                runCatching { out.close() }
            }
        }
    }

    fun startPlaying(input: InputStream) {
        running = true
        playThread = thread(name = "speaker-player") {
            val minBuf = AudioTrack.getMinBufferSize(
                SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT
            )
            val track = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setSampleRate(SAMPLE_RATE)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .build()
                )
                .setBufferSizeInBytes(minBuf * 2)
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()

            val buffer = ByteArray(SAMPLE_RATE / 50 * 2)
            try {
                track.play()
                while (running) {
                    val n = input.read(buffer)
                    if (n < 0) break
                    if (n > 0) track.write(buffer, 0, n)
                }
            } catch (_: Exception) {
                // Stream closed: the call ended.
            } finally {
                runCatching { track.stop() }
                track.release()
                runCatching { input.close() }
            }
        }
    }

    fun stop() {
        running = false
        muted = false
        recordThread = null
        playThread = null
    }
}

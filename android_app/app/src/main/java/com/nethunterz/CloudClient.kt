package com.nethunterz

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.logging.HttpLoggingInterceptor
import java.util.concurrent.TimeUnit

private const val TAG = "CloudClient"
private val JSON_TYPE = "application/json; charset=utf-8".toMediaType()

/**
 * CloudClient – Communicates with the NetHunterZ cloud API server.
 *
 * Endpoints used:
 *  GET  /api/v1/status
 *  GET  /api/v1/recommendations
 *  POST /api/v1/packets
 */
class CloudClient(
    private val baseUrl: String = "https://cloud.nethunterz.example.com",
    private val apiKey: String = "",
) {
    private val gson = Gson()
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .addInterceptor(HttpLoggingInterceptor { Log.d(TAG, it) }.apply {
            level = HttpLoggingInterceptor.Level.BODY
        })
        .build()

    // -----------------------------------------------------------------------

    suspend fun getStatus(): Result<CloudServiceStatus> = withContext(Dispatchers.IO) {
        runCatching {
            val req = buildGet("/api/v1/status")
            val body = http.newCall(req).execute().use { it.body?.string() ?: "{}" }
            val json = gson.fromJson(body, JsonObject::class.java)
            CloudServiceStatus(running = json["running"]?.asBoolean ?: false)
        }
    }

    suspend fun getRecommendations(deviceId: String): Result<List<FrequencyRecommendation>> =
        withContext(Dispatchers.IO) {
            runCatching {
                val req = buildGet("/api/v1/recommendations?device_id=$deviceId")
                val body = http.newCall(req).execute().use { it.body?.string() ?: "{}" }
                val json = gson.fromJson(body, JsonObject::class.java)
                val recs = json.getAsJsonArray("recommendations") ?: return@runCatching emptyList()
                recs.map { el ->
                    val obj = el.asJsonObject
                    FrequencyRecommendation(
                        moduleId = obj["module_id"].asInt,
                        channel = obj["channel"].asInt,
                        frequencyMhz = obj["frequency_mhz"].asDouble,
                        reason = obj["reason"].asString,
                    )
                }
            }
        }

    suspend fun uploadPackets(deviceId: String, packets: List<PacketItem>): Result<Unit> =
        withContext(Dispatchers.IO) {
            runCatching {
                val payload = gson.toJson(
                    mapOf(
                        "device_id" to deviceId,
                        "packets" to packets.map {
                            mapOf(
                                "channel" to it.channel,
                                "frequency_mhz" to it.freqMhz,
                                "rssi" to it.rssi,
                                "payload" to it.payload,
                                "module_id" to it.moduleId,
                                "timestamp" to it.timestampMs / 1000.0,
                            )
                        }
                    )
                )
                val req = Request.Builder()
                    .url("$baseUrl/api/v1/packets")
                    .addHeader("Authorization", "Bearer $apiKey")
                    .post(payload.toRequestBody(JSON_TYPE))
                    .build()
                http.newCall(req).execute().close()
            }
        }

    // -----------------------------------------------------------------------

    private fun buildGet(path: String) = Request.Builder()
        .url("$baseUrl$path")
        .addHeader("Authorization", "Bearer $apiKey")
        .get()
        .build()
}

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

data class CloudServiceStatus(val running: Boolean)

data class FrequencyRecommendation(
    val moduleId: Int,
    val channel: Int,
    val frequencyMhz: Double,
    val reason: String,
)

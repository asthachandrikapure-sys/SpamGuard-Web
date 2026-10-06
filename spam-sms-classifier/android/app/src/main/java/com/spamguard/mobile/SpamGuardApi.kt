package com.spamguard.mobile

import android.content.Context
import com.google.gson.annotations.SerializedName
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit

data class PredictionRequest(
    val message: String,
    val sender: String? = null,
    @SerializedName("mobile_number") val mobileNumber: String? = null,
    @SerializedName("device_id") val deviceId: String? = null,
    @SerializedName("device_token") val deviceToken: String? = null
)

data class HeartbeatRequest(
    @SerializedName("monitoring_active") val monitoringActive: Boolean,
    @SerializedName("mobile_number") val mobileNumber: String? = null,
    @SerializedName("device_token") val deviceToken: String? = null
)

data class Prediction(
    val id: Long = 0,
    val message: String = "",
    val sender: String = "",
    val prediction: String = "",
    val confidence: Double = 0.0,
    @SerializedName("risk_level") val riskLevel: String = "LOW",
    val model: String = "",
    @SerializedName("created_at") val createdAt: String = ""
)

data class DashboardStats(
    @SerializedName("total_messages") val totalMessages: Int = 0,
    @SerializedName("spam_messages") val spamMessages: Int = 0,
    @SerializedName("ham_messages") val hamMessages: Int = 0,
    @SerializedName("high_risk_messages") val highRiskMessages: Int = 0
)

data class ProtectionStatus(
    @SerializedName("phone_connected") val phoneConnected: Boolean = false,
    @SerializedName("monitoring_active") val monitoringActive: Boolean = false,
    @SerializedName("protection_active") val protectionActive: Boolean = false,
    @SerializedName("ml_active") val mlActive: Boolean = false,
    @SerializedName("last_seen") val lastSeen: String? = null
)

data class DailyAnalytics(
    val day: String = "",
    val total: Int = 0,
    val spam: Int = 0,
    val ham: Int = 0
)

data class Analytics(
    val daily: List<DailyAnalytics> = emptyList(),
    @SerializedName("risk_levels") val riskLevels: Map<String, Int> = emptyMap(),
    @SerializedName("average_confidence") val averageConfidence: Double = 0.0
)

interface SpamGuardService {
    @POST("api/predict")
    suspend fun classify(@Body request: PredictionRequest): Prediction

    @GET("api/history")
    suspend fun history(): List<Prediction>

    @GET("api/stats")
    suspend fun stats(): DashboardStats

    @GET("api/analytics")
    suspend fun analytics(): Analytics

    @GET("api/protection-status")
    suspend fun protectionStatus(): ProtectionStatus

    @POST("api/device/heartbeat")
    suspend fun heartbeat(@Body request: HeartbeatRequest): ProtectionStatus
}

object SpamGuardApi {
    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val httpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private val serviceCache = ConcurrentHashMap<String, SpamGuardService>()

    fun getService(context: Context): SpamGuardService {
        val baseUrl = ProtectionPreferences.getApiBaseUrl(context)
        return serviceCache.getOrPut(baseUrl) {
            Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(httpClient)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(SpamGuardService::class.java)
        }
    }

    val service: SpamGuardService by lazy {
        val defaultUrl = BuildConfig.API_BASE_URL
        Retrofit.Builder()
            .baseUrl(if (defaultUrl.endsWith("/")) defaultUrl else "$defaultUrl/")
            .client(httpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(SpamGuardService::class.java)
    }
}


package com.spamguard.mobile

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import org.json.JSONObject
import retrofit2.HttpException
import java.io.IOException

data class ScreenState(
    val predictions: List<Prediction> = emptyList(),
    val stats: DashboardStats = DashboardStats(),
    val analytics: Analytics = Analytics(),
    val protection: ProtectionStatus = ProtectionStatus(),
    val isRefreshing: Boolean = false,
    val errorMessage: String? = null,
    val apiConnected: Boolean? = null,
    val apiMessage: String = "Not checked yet"
)

class SpamGuardViewModel(application: Application) : AndroidViewModel(application) {
    var state = androidx.compose.runtime.mutableStateOf(ScreenState())
        private set

    fun refresh() {
        if (state.value.isRefreshing) return
        viewModelScope.launch { refreshData() }
    }

    fun reportMonitoringState(enabled: Boolean) {
        viewModelScope.launch {
            try {
                val app = getApplication<Application>()
                val api = SpamGuardApi.getService(app)
                val simNumber = ProtectionPreferences.getSimNumber(app)
                val deviceToken = ProtectionPreferences.getDeviceToken(app)
                val protection = api.heartbeat(
                    HeartbeatRequest(
                        monitoringActive = enabled,
                        mobileNumber = simNumber,
                        deviceToken = deviceToken
                    )
                )
                state.value = state.value.copy(
                    protection = protection,
                    apiConnected = true,
                    apiMessage = "Connected to SpamGuard API"
                )
                refreshData()
            } catch (error: Exception) {
                state.value = state.value.copy(apiConnected = false, apiMessage = readableError(error))
            }
        }
    }

    private suspend fun refreshData() {
        state.value = state.value.copy(isRefreshing = true)
        val app = getApplication<Application>()
        val api = SpamGuardApi.getService(app)
        var apiResponded = false
        var failureMessage: String? = null
        try {
            val stats = api.stats()
            state.value = state.value.copy(stats = stats)
            apiResponded = true
        } catch (error: Exception) {
            failureMessage = readableError(error)
        }
        try {
            val history = api.history()
            state.value = state.value.copy(predictions = history)
            apiResponded = true
        } catch (error: Exception) {
            failureMessage = failureMessage ?: readableError(error)
        }
        try {
            state.value = state.value.copy(protection = api.protectionStatus())
            apiResponded = true
        } catch (error: Exception) {
            failureMessage = failureMessage ?: readableError(error)
        }
        try {
            state.value = state.value.copy(analytics = api.analytics())
            apiResponded = true
        } catch (error: Exception) {
            failureMessage = failureMessage ?: readableError(error)
        }
        state.value = state.value.copy(
            isRefreshing = false,
            apiConnected = apiResponded,
            apiMessage = if (apiResponded) "Connected to SpamGuard API" else failureMessage ?: "SpamGuard API is unavailable"
        )
    }

    private fun readableError(error: Exception): String = when (error) {
        is HttpException -> {
            val body = error.response()?.errorBody()?.string()
            runCatching { JSONObject(body.orEmpty()).optString("error") }
                .getOrNull()
                ?.takeIf(String::isNotBlank)
                ?: "The SpamGuard server returned an error (${error.code()})."
        }
        is IOException -> "Could not reach SpamGuard at ${ProtectionPreferences.getApiBaseUrl(getApplication())}. Check your network connection."
        else -> error.message ?: "Something went wrong. Please try again."
    }
}


package com.spamguard.mobile

import android.content.Context

object ProtectionPreferences {
    private const val FILE_NAME = "spamguard_settings"
    private const val KEY_AUTOMATIC_CHECKING = "automatic_checking_enabled"
    private const val KEY_NOTIFICATIONS_ENABLED = "spam_notifications_enabled"
    private const val KEY_API_BASE_URL = "api_base_url"
    private const val KEY_SIM_NUMBER = "sim_mobile_number"
    private const val KEY_DEVICE_TOKEN = "device_token"

    fun isAutomaticCheckingEnabled(context: Context): Boolean =
        context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
            .getBoolean(KEY_AUTOMATIC_CHECKING, true)

    fun setAutomaticCheckingEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_AUTOMATIC_CHECKING, enabled)
            .apply()
    }

    fun areNotificationsEnabled(context: Context): Boolean =
        context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
            .getBoolean(KEY_NOTIFICATIONS_ENABLED, true)

    fun setNotificationsEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_NOTIFICATIONS_ENABLED, enabled)
            .apply()
    }

    fun getApiBaseUrl(context: Context): String {
        val stored = context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
            .getString(KEY_API_BASE_URL, null)
        val url = if (!stored.isNullOrBlank()) stored.trim() else BuildConfig.API_BASE_URL
        return if (url.endsWith("/")) url else "$url/"
    }

    fun setApiBaseUrl(context: Context, url: String) {
        val sanitized = if (url.trim().endsWith("/")) url.trim() else "${url.trim()}/"
        context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_API_BASE_URL, sanitized)
            .apply()
    }

    fun getSimNumber(context: Context): String =
        context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
            .getString(KEY_SIM_NUMBER, "9503564504") ?: "9503564504"

    fun setSimNumber(context: Context, number: String) {
        context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_SIM_NUMBER, number.trim())
            .apply()
    }

    fun getDeviceToken(context: Context): String =
        context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
            .getString(KEY_DEVICE_TOKEN, "SPAMGUARD-DEV-9503564504") ?: "SPAMGUARD-DEV-9503564504"
}


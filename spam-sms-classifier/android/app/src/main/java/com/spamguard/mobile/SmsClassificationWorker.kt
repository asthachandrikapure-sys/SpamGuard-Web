package com.spamguard.mobile

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import org.json.JSONObject
import retrofit2.HttpException
import java.io.IOException

class SmsClassificationWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {
    override suspend fun doWork(): Result {
        val message = inputData.getString(SMS_MESSAGE_INPUT)?.trim().orEmpty()
        if (message.isEmpty()) return Result.failure()
        val sender = inputData.getString(SMS_SENDER_INPUT)
        val simNumber = ProtectionPreferences.getSimNumber(applicationContext)
        val deviceToken = ProtectionPreferences.getDeviceToken(applicationContext)

        android.util.Log.i("SPAMGUARD", "WorkManager processing SMS from $sender...")
        return try {
            val api = SpamGuardApi.getService(applicationContext)
            val request = PredictionRequest(
                message = message,
                sender = sender,
                mobileNumber = simNumber,
                deviceId = deviceToken,
                deviceToken = deviceToken
            )
            val prediction = api.classify(request)
            android.util.Log.i("SPAMGUARD", "SPAMGUARD: Backend response (worker) = prediction=${prediction.prediction}, confidence=${prediction.confidence}, risk=${prediction.riskLevel}")

            if (prediction.prediction.equals("spam", ignoreCase = true) &&
                ProtectionPreferences.areNotificationsEnabled(applicationContext)
            ) {
                SpamGuardNotifications.showResult(applicationContext, prediction)
            }
            Result.success()
        } catch (error: HttpException) {
            val serverMessage = runCatching {
                JSONObject(error.response()?.errorBody()?.string().orEmpty()).optString("error")
            }.getOrNull().orEmpty()
            android.util.Log.e("SPAMGUARD", "WorkManager HTTP error: ${error.code()} - $serverMessage")
            if (error.code() >= 500) {
                Result.retry()
            } else {
                SpamGuardNotifications.showFailure(
                    applicationContext,
                    serverMessage.ifBlank { "The SMS could not be classified." }
                )
                Result.failure()
            }
        } catch (error: IOException) {
            android.util.Log.e("SPAMGUARD", "WorkManager network error: ${error.message}")
            Result.retry()
        } catch (error: Exception) {
            android.util.Log.e("SPAMGUARD", "WorkManager unexpected error: ${error.message}", error)
            SpamGuardNotifications.showFailure(
                applicationContext,
                error.message ?: "The SMS could not be classified."
            )
            Result.failure()
        }
    }
}

object SpamGuardNotifications {
    private const val CHANNEL_ID = "spamguard_sms_results"

    fun showResult(context: Context, prediction: Prediction) {
        val label = if (prediction.prediction.equals("spam", ignoreCase = true)) "SPAM DETECTED" else "SAFE MESSAGE"
        val details = "${(prediction.confidence * 100).toInt()}% confidence · Risk ${prediction.riskLevel}"
        show(context, label, details, isWarning = prediction.riskLevel.equals("HIGH", ignoreCase = true))
    }

    fun showFailure(context: Context, message: String) {
        show(context, "SMS check needs attention", message, isWarning = true)
    }

    private fun show(context: Context, title: String, text: String, isWarning: Boolean) {
        if (!ProtectionPreferences.areNotificationsEnabled(context)) return
        if (android.os.Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(
                android.app.NotificationChannel(
                    CHANNEL_ID,
                    "SMS classification results",
                    android.app.NotificationManager.IMPORTANCE_DEFAULT
                ).apply { description = "Results from opted-in incoming SMS checks" }
            )
        }

        val openApp = android.app.PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java),
            android.app.PendingIntent.FLAG_UPDATE_CURRENT or android.app.PendingIntent.FLAG_IMMUTABLE
        )
        val notification = androidx.core.app.NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(if (isWarning) android.R.drawable.stat_notify_error else android.R.drawable.stat_notify_chat)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(androidx.core.app.NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(openApp)
            .setAutoCancel(true)
            .setPriority(androidx.core.app.NotificationCompat.PRIORITY_DEFAULT)
            .build()
        manager.notify((System.currentTimeMillis() % Int.MAX_VALUE).toInt(), notification)
    }
}

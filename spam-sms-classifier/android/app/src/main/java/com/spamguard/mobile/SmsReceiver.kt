package com.spamguard.mobile

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.util.UUID

const val SMS_MESSAGE_INPUT = "incoming_sms_message"
const val SMS_SENDER_INPUT = "incoming_sms_sender"

class SmsReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "SPAMGUARD"

        // Optional listener so MainActivity / UI can refresh immediately when SMS is processed
        var onSmsProcessedListener: ((Prediction) -> Unit)? = null
    }

    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action
        if (action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) {
            return
        }

        val smsParts = try {
            Telephony.Sms.Intents.getMessagesFromIntent(intent)
        } catch (e: Exception) {
            Log.e(TAG, "Error extracting SMS from intent: ${e.message}", e)
            null
        }

        if (smsParts.isNullOrEmpty()) {
            Log.w(TAG, "SMS intent received but no messages were parsed.")
            return
        }

        val sender = smsParts.firstOrNull()?.originatingAddress.orEmpty()
        val message = smsParts.joinToString(separator = "") { it.messageBody.orEmpty() }
            .trim()
            .take(1000)

        // Log exact required messages for first success condition
        Log.i(TAG, "==================================================")
        Log.i(TAG, "SPAMGUARD: SMS RECEIVED")
        Log.i(TAG, "SPAMGUARD: Sender = $sender")
        Log.i(TAG, "SPAMGUARD: SMS captured")
        Log.i(TAG, "Message Body: $message")

        if (message.isEmpty()) {
            Log.w(TAG, "SMS message body is empty, skipping classification.")
            return
        }

        val isAutoChecking = ProtectionPreferences.isAutomaticCheckingEnabled(context)
        if (!isAutoChecking) {
            Log.w(TAG, "SPAMGUARD: Automatic checking is DISABLED in settings. Enable it to send to backend.")
            return
        }

        val pendingResult = goAsync()
        val simNumber = ProtectionPreferences.getSimNumber(context)
        val deviceToken = ProtectionPreferences.getDeviceToken(context)
        val baseUrl = ProtectionPreferences.getApiBaseUrl(context)

        Log.i(TAG, "SPAMGUARD: Sending to backend")
        Log.i(TAG, "Target API: $baseUrl | SIM: $simNumber | Device: $deviceToken")

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val apiService = SpamGuardApi.getService(context)
                val request = PredictionRequest(
                    message = message,
                    sender = sender,
                    mobileNumber = simNumber,
                    deviceId = deviceToken,
                    deviceToken = deviceToken
                )

                val prediction = apiService.classify(request)

                Log.i(TAG, "SPAMGUARD: Backend response = prediction=${prediction.prediction}, confidence=${prediction.confidence}, risk=${prediction.riskLevel}, id=${prediction.id}")
                Log.i(TAG, "==================================================")

                // Show notification if classified as spam
                if (prediction.prediction.equals("spam", ignoreCase = true) &&
                    ProtectionPreferences.areNotificationsEnabled(context)
                ) {
                    SpamGuardNotifications.showResult(context, prediction)
                }

                // Notify UI listener if active
                try {
                    onSmsProcessedListener?.invoke(prediction)
                } catch (_: Exception) {}

            } catch (error: Exception) {
                Log.e(TAG, "SPAMGUARD: Direct backend call failed: ${error.message}", error)
                Log.i(TAG, "SPAMGUARD: Enqueuing WorkManager fallback...")
                enqueueFallbackWork(context, message, sender)
            } finally {
                pendingResult.finish()
            }
        }
    }

    private fun enqueueFallbackWork(context: Context, message: String, sender: String) {
        val request = OneTimeWorkRequestBuilder<SmsClassificationWorker>()
            .setInputData(workDataOf(SMS_MESSAGE_INPUT to message, SMS_SENDER_INPUT to sender))
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
            )
            .build()

        WorkManager.getInstance(context).enqueueUniqueWork(
            "classify-incoming-sms-${UUID.randomUUID()}",
            ExistingWorkPolicy.KEEP,
            request
        )
    }
}


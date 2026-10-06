package com.spamguard.mobile

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.io.IOException
import java.util.concurrent.TimeUnit

object ProtectionHeartbeat {
    private const val WORK_NAME = "spamguard-phone-heartbeat"

    fun schedule(context: Context) {
        val request = PeriodicWorkRequestBuilder<ProtectionHeartbeatWorker>(15, TimeUnit.MINUTES)
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
            )
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            WORK_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,
            request
        )
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
    }
}

class ProtectionHeartbeatWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {
    override suspend fun doWork(): Result {
        if (!ProtectionPreferences.isAutomaticCheckingEnabled(applicationContext)) return Result.success()
        val simNumber = ProtectionPreferences.getSimNumber(applicationContext)
        val deviceToken = ProtectionPreferences.getDeviceToken(applicationContext)
        return try {
            val api = SpamGuardApi.getService(applicationContext)
            api.heartbeat(
                HeartbeatRequest(
                    monitoringActive = true,
                    mobileNumber = simNumber,
                    deviceToken = deviceToken
                )
            )
            Result.success()
        } catch (error: IOException) {
            Result.retry()
        } catch (error: retrofit2.HttpException) {
            if (error.code() >= 500) Result.retry() else Result.failure()
        }
    }
}

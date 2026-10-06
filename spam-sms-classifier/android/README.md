# SpamGuard Android App

A native Kotlin/Jetpack Compose client for the existing SpamGuard Flask service. The phone never contains the classifier, model files, database connection, or database credentials.

## Project layout

- `app/src/main/AndroidManifest.xml`: network, SMS, and notification permission declarations plus the incoming-SMS receiver.
- `app/src/main/java/com/spamguard/mobile/MainActivity.kt`: Home, Live Protection, SMS History, Analytics, Settings, and runtime permission flow. There is no manual message checker.
- `SpamGuardApi.kt`: Retrofit models and HTTPS API client.
- `SmsReceiver.kt`: receives new SMS broadcasts only when the user enabled automatic checking, then queues work.
- `SmsClassificationWorker.kt`: sends the message and masked-sender candidate to Flask and posts spam warnings; retries network/server errors.
- `ProtectionHeartbeat.kt`: reports the enabled monitoring state when the app is active and periodically while protection is enabled.
- `SpamGuardViewModel.kt`: protection status, dashboard/history refresh, loading and error state.

## Open and run

1. Deploy the latest Flask backend to Render first. It must serve `POST /api/predict`, `GET /api/history`, `GET /api/stats`, `GET /api/analytics`, `GET /api/protection-status`, and `POST /api/device/heartbeat`. Before testing the phone, confirm `https://spamguard-web.onrender.com/api/stats` returns HTTP 200. It currently returns HTTP 503 because Render cannot reach MySQL. Configure a remotely reachable MySQL host and credentials in Render's environment settings, then redeploy. A local MySQL password alone does not make the local database reachable from Render.
2. Install Android Studio with Android SDK Platform 35 and JDK 17.
3. Open this `android/` directory in Android Studio and allow Gradle sync to finish.
4. Connect a physical Android phone with USB debugging enabled, select it in Android Studio, then choose **Run**.
5. In SpamGuard, open Settings or tap **Grant permission and enable** on Home. Allow SMS access, then allow notifications if prompted. Automatic checks are off until the user opts in.
6. Send a test SMS to the phone from another device. When the phone has internet access, SpamGuard queues it for classification. Spam results generate a notification with confidence and risk. SMS History shows only the masked sender and redacted, truncated preview. Dashboard and Analytics values come from the backend database and update automatically.

The app has no manual message-entry feature. Without SMS permission or opt-in, incoming messages are not submitted.

## API URL

The public, non-secret API base URL is set in `app/build.gradle.kts` as `BuildConfig.API_BASE_URL`:

```text
https://spamguard-web.onrender.com/
```

If the Render service URL changes, update that build config value and sync/rebuild. The app makes these requests:

- `POST api/predict` with `{"message":"..."}`
- `GET api/history`
- `GET api/stats`
- `GET api/analytics`
- `GET api/protection-status`
- `POST api/device/heartbeat` with `{"monitoring_active":true}`

The phone only stores the user's automatic-check preference locally. It has no MySQL host, password, database name, model artifact, or server secret.

## Permissions and user control

- `INTERNET`: required to use the HTTPS Flask API.
- `RECEIVE_SMS`: runtime permission used only for newly received messages. SpamGuard does not request `READ_SMS`, so it does not scan the existing inbox.
- `POST_NOTIFICATIONS`: requested on Android 13+ to show completed automatic classifications. If denied, classifications can still be reviewed in the app.

Automatic checking is **off by default**. Turning it on requires explicit SMS permission. Turning it off stops processing future incoming messages and heartbeats. SpamGuard never deletes, modifies, forwards, or sends SMS messages. Incoming SMS text is transmitted only to the configured HTTPS backend while automatic checking is enabled; the backend uses the original text for inference, then stores and returns only a truncated preview with numeric codes redacted and the sender masked.

## Real-device test

Use a phone with an active SIM and mobile data or Wi-Fi. Grant `RECEIVE_SMS`, enable automatic checking in Settings, then send a plain text message from a second phone. Verify a spam notification when appropriate, the new masked row in SMS History, and updated dashboard/analytics values. Also test with airplane mode enabled: work waits for a network connection and retries transient failures. Turn automatic checking off and confirm later messages are not submitted.

## Distribution note

Android restricts SMS permissions, and Google Play generally permits `RECEIVE_SMS` only when the app is an eligible default SMS handler or qualifies for an approved exception. This project does not replace the user's SMS app. Sideload/internal demonstration installs can request user permission, but Play publication requires reviewing and meeting the current SMS/Call Log policy. Never try to bypass Android permission prompts or policy controls.

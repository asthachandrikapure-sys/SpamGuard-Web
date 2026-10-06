package com.spamguard.mobile

import android.Manifest
import android.content.Context
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Telephony
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Mail
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import java.util.Locale

private val GuardBackground = Color(0xFF0D1510)
private val GuardSurface = Color(0xFF18231B)
private val GuardAccent = Color(0xFFB8E66B)
private val GuardText = Color(0xFFF0F4ED)
private val GuardMuted = Color(0xFF9BA99C)
private val GuardRed = Color(0xFFFF806C)
private val GuardGreen = Color(0xFF79D4AA)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { SpamGuardTheme { SpamGuardApp() } }
    }
}

private data class Destination(val route: String, val label: String, val icon: ImageVector)

private val destinations = listOf(
    Destination("home", "Home", Icons.Default.Home),
    Destination("history", "History", Icons.Default.History),
    Destination("analytics", "Analytics", Icons.Default.BarChart),
    Destination("settings", "Settings", Icons.Default.Settings)
)

@Composable
private fun SpamGuardTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = GuardAccent,
            onPrimary = Color(0xFF1A2412),
            secondary = GuardGreen,
            background = GuardBackground,
            surface = GuardSurface,
            onBackground = GuardText,
            onSurface = GuardText,
            error = GuardRed
        ),
        content = content
    )
}

@Composable
private fun SpamGuardApp(viewModel: SpamGuardViewModel = viewModel()) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val navController = rememberNavController()
    val state = viewModel.state.value
    var smsPermissionGranted by remember {
        mutableStateOf(hasSmsPermission(context))
    }
    var automaticChecksEnabled by remember {
        mutableStateOf(ProtectionPreferences.isAutomaticCheckingEnabled(context))
    }
    var notificationsEnabled by remember {
        mutableStateOf(ProtectionPreferences.areNotificationsEnabled(context))
    }
    var pendingEnable by remember { mutableStateOf(false) }

    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }

    val requestNotifications = {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    val smsPermissions = arrayOf(
        Manifest.permission.RECEIVE_SMS,
        Manifest.permission.READ_SMS
    )

    val smsPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        val granted = results[Manifest.permission.RECEIVE_SMS] == true
        smsPermissionGranted = granted
        if (granted) {
            ProtectionPreferences.setAutomaticCheckingEnabled(context, true)
            automaticChecksEnabled = true
            ProtectionHeartbeat.schedule(context)
            viewModel.reportMonitoringState(true)
            requestNotifications()
        }
        pendingEnable = false
    }

    fun updateAutomaticChecks(enabled: Boolean) {
        if (enabled && !smsPermissionGranted) {
            pendingEnable = true
            smsPermissionLauncher.launch(smsPermissions)
        } else {
            ProtectionPreferences.setAutomaticCheckingEnabled(context, enabled)
            automaticChecksEnabled = enabled
            if (enabled) {
                ProtectionHeartbeat.schedule(context)
                requestNotifications()
            } else {
                ProtectionHeartbeat.cancel(context)
            }
            viewModel.reportMonitoringState(enabled)
        }
    }

    fun enableProtection() {
        if (smsPermissionGranted) {
            updateAutomaticChecks(true)
        } else {
            pendingEnable = true
            smsPermissionLauncher.launch(smsPermissions)
        }
    }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                smsPermissionGranted = hasSmsPermission(context)
                automaticChecksEnabled = ProtectionPreferences.isAutomaticCheckingEnabled(context)
                notificationsEnabled = ProtectionPreferences.areNotificationsEnabled(context)
                if (automaticChecksEnabled && smsPermissionGranted) ProtectionHeartbeat.schedule(context)
                viewModel.reportMonitoringState(automaticChecksEnabled && smsPermissionGranted)
                viewModel.refresh()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)

        // Dynamic SMS receiver registration while app is active for instant detection
        val dynamicReceiver = SmsReceiver()
        val filter = IntentFilter(Telephony.Sms.Intents.SMS_RECEIVED_ACTION).apply {
            priority = 999
        }
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                context.registerReceiver(dynamicReceiver, filter, Context.RECEIVER_EXPORTED)
            } else {
                context.registerReceiver(dynamicReceiver, filter)
            }
            Log.i("SPAMGUARD", "Dynamic SMS receiver registered successfully")
        } catch (e: Exception) {
            Log.e("SPAMGUARD", "Could not register dynamic SMS receiver: ${e.message}")
        }

        SmsReceiver.onSmsProcessedListener = {
            viewModel.refresh()
        }

        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            try {
                context.unregisterReceiver(dynamicReceiver)
            } catch (_: Exception) {}
            SmsReceiver.onSmsProcessedListener = null
        }
    }

    LaunchedEffect(Unit) {
        // Automatically prompt for SMS permission on initial launch if not granted
        if (!hasSmsPermission(context)) {
            smsPermissionLauncher.launch(smsPermissions)
        }
        viewModel.refresh()
        while (true) {
            kotlinx.coroutines.delay(15000)
            viewModel.refresh()
        }
    }

    val currentRoute = navController.currentBackStackEntryAsState().value?.destination?.route
    Scaffold(
        containerColor = GuardBackground,
        bottomBar = {
            NavigationBar(containerColor = GuardSurface) {
                destinations.forEach { destination ->
                    NavigationBarItem(
                        selected = currentRoute == destination.route,
                        onClick = {
                            navController.navigate(destination.route) {
                                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { androidx.compose.material3.Icon(destination.icon, contentDescription = destination.label) },
                        label = { Text(destination.label, maxLines = 1, fontSize = 10.sp) }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = "home",
            modifier = Modifier.padding(innerPadding)
        ) {
            composable("home") {
                HomeScreen(
                    state = state,
                    smsPermissionGranted = smsPermissionGranted,
                    automaticChecksEnabled = automaticChecksEnabled,
                    onEnableProtection = ::enableProtection,
                    onOpenProtection = { navController.navigate("protection") },
                    onOpenSettings = { navController.navigate("settings") },
                    onRefresh = viewModel::refresh
                )
            }
            composable("protection") { LiveProtectionScreen(state, smsPermissionGranted, automaticChecksEnabled) }
            composable("history") { HistoryScreen(state, viewModel::refresh) }
            composable("analytics") { DashboardScreen(state, viewModel::refresh) }
            composable("settings") {
                SettingsScreen(
                    state = state,
                    smsPermissionGranted = smsPermissionGranted,
                    automaticChecksEnabled = automaticChecksEnabled,
                    notificationsEnabled = notificationsEnabled,
                    onNotificationsChanged = { enabled ->
                        ProtectionPreferences.setNotificationsEnabled(context, enabled)
                        notificationsEnabled = enabled
                        if (enabled) requestNotifications()
                    },
                    onAutomaticChecksChanged = ::updateAutomaticChecks,
                    onRequestPermission = {
                        pendingEnable = false
                        smsPermissionLauncher.launch(smsPermissions)
                    },
                    onRefresh = viewModel::refresh
                )
            }
        }
    }
}

private fun hasSmsPermission(context: android.content.Context): Boolean =
    ContextCompat.checkSelfPermission(context, Manifest.permission.RECEIVE_SMS) == PackageManager.PERMISSION_GRANTED


@Composable
private fun PageColumn(contentPadding: PaddingValues = PaddingValues(20.dp), content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(GuardBackground)
            .verticalScroll(rememberScrollState())
            .padding(contentPadding),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        content = content
    )
}

@Composable
private fun PageHeading(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text(subtitle, color = GuardMuted, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun HomeScreen(
    state: ScreenState,
    smsPermissionGranted: Boolean,
    automaticChecksEnabled: Boolean,
    onEnableProtection: () -> Unit,
    onOpenProtection: () -> Unit,
    onOpenSettings: () -> Unit,
    onRefresh: () -> Unit
) {
    PageColumn {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Surface(shape = RoundedCornerShape(14.dp), color = GuardAccent, modifier = Modifier.size(48.dp)) {
                Box(contentAlignment = Alignment.Center) {
                    androidx.compose.material3.Icon(Icons.Default.Shield, contentDescription = null, tint = Color(0xFF17200F))
                }
            }
            Column {
                Text("SpamGuard", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text("Real-time SMS protection", color = GuardMuted, style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.weight(1f))
            androidx.compose.material3.IconButton(onClick = onRefresh, enabled = !state.isRefreshing) {
                androidx.compose.material3.Icon(Icons.Default.Refresh, contentDescription = "Refresh")
            }
        }

        ProtectionCard(
            smsPermissionGranted = smsPermissionGranted,
            automaticChecksEnabled = automaticChecksEnabled,
            onAction = if (!smsPermissionGranted || !automaticChecksEnabled) onEnableProtection else onOpenSettings
        )

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MetricCard("SMS scanned", state.stats.totalMessages.toString(), Icons.Default.Mail, Modifier.weight(1f))
            MetricCard("Spam detected", state.stats.spamMessages.toString(), Icons.Default.Warning, Modifier.weight(1f), warning = true)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MetricCard("Safe messages", state.stats.hamMessages.toString(), Icons.Default.CheckCircle, Modifier.weight(1f))
            MetricCard("High risk", state.stats.highRiskMessages.toString(), Icons.Default.Shield, Modifier.weight(1f), warning = true)
        }

        OutlinedButton(onClick = onOpenProtection, modifier = Modifier.fillMaxWidth().height(50.dp)) {
            Text("View Live Protection")
        }
        ApiConnectionLine(state.apiConnected, state.apiMessage)
        if (state.errorMessage != null) ErrorNotice(state.errorMessage)

        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Recent detections", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                Text("Last scan: ${state.predictions.firstOrNull()?.createdAt ?: "No scans yet"}", color = GuardMuted, style = MaterialTheme.typography.bodySmall)
            }
            androidx.compose.material3.TextButton(onClick = onOpenSettings) { Text("Settings") }
        }
        if (state.predictions.isEmpty()) {
            EmptyState("No detections yet", "New incoming SMS classifications will appear here.")
        } else {
            state.predictions.take(3).forEach { HistoryCard(it) }
        }
    }
}

@Composable
private fun ProtectionCard(
    smsPermissionGranted: Boolean,
    automaticChecksEnabled: Boolean,
    onAction: () -> Unit
) {
    val active = smsPermissionGranted && automaticChecksEnabled
    Card(
        colors = CardDefaults.cardColors(containerColor = if (active) Color(0xFF1A3024) else Color(0xFF2B271B)),
        shape = RoundedCornerShape(18.dp)
    ) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                androidx.compose.material3.Icon(
                    if (active) Icons.Default.CheckCircle else Icons.Default.Warning,
                    contentDescription = null,
                    tint = if (active) GuardGreen else Color(0xFFE8C46C)
                )
                Column(Modifier.weight(1f)) {
                    Text(if (active) "Automatic protection is on" else "Automatic protection is off", fontWeight = FontWeight.SemiBold)
                    Text(
                        when {
                            !smsPermissionGranted -> "SMS permission has not been granted."
                            !automaticChecksEnabled -> "SMS access is allowed, but automatic checks are paused."
                            else -> "New incoming SMS messages are checked with your permission."
                        },
                        color = GuardMuted,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
            if (!active) {
                OutlinedButton(onClick = onAction, modifier = Modifier.fillMaxWidth()) {
                    Text(if (!smsPermissionGranted) "Grant permission and enable" else "Enable automatic checks")
                }
            }
        }
    }
}

@Composable
private fun LiveProtectionScreen(
    state: ScreenState,
    smsPermissionGranted: Boolean,
    automaticChecksEnabled: Boolean
) {
    PageColumn {
        PageHeading("Live Protection", "Connection and classification services for this phone.")
        val phoneConnected = state.protection.phoneConnected
        val monitoringActive = smsPermissionGranted && automaticChecksEnabled && state.protection.monitoringActive
        val mlActive = state.protection.mlActive
        StatusCard("Phone connection", if (phoneConnected) "Connected" else "Not connected", phoneConnected)
        StatusCard("SMS monitoring", if (monitoringActive) "Active" else "Inactive", monitoringActive)
        StatusCard("ML protection", if (mlActive) "Active" else "Unavailable", mlActive)
        Text(
            "Last phone heartbeat: ${state.protection.lastSeen ?: "Not received"}",
            color = GuardMuted,
            style = MaterialTheme.typography.bodySmall
        )
        if (!smsPermissionGranted || !automaticChecksEnabled) {
            ErrorNotice("Enable SMS permission and automatic protection in Settings to scan new incoming messages.")
        }
        Text("Last received SMS classification", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        state.predictions.firstOrNull()?.let { HistoryCard(it) }
            ?: EmptyState("No classifications yet", "New results from the phone will appear here.")
        if (state.apiConnected == false) ErrorNotice(state.apiMessage)
    }
}

@Composable
private fun StatusCard(label: String, value: String, active: Boolean) {
    Card(colors = CardDefaults.cardColors(containerColor = GuardSurface), shape = RoundedCornerShape(14.dp)) {
        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Surface(shape = CircleShape, color = if (active) GuardGreen else GuardMuted, modifier = Modifier.size(9.dp)) { }
            Text(label, modifier = Modifier.weight(1f), color = GuardMuted)
            Text(value, fontWeight = FontWeight.SemiBold, color = if (active) GuardGreen else GuardRed)
        }
    }
}

@Composable
private fun HistoryScreen(state: ScreenState, onRefresh: () -> Unit) {
    Column(
        Modifier.fillMaxSize().background(GuardBackground).padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("SMS History", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                Text("Classifications saved by the Flask API", color = GuardMuted)
            }
            androidx.compose.material3.IconButton(onClick = onRefresh, enabled = !state.isRefreshing) {
                androidx.compose.material3.Icon(Icons.Default.Refresh, contentDescription = "Refresh history")
            }
        }
        if (state.isRefreshing && state.predictions.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        } else if (state.predictions.isEmpty()) {
            EmptyState("No SMS classifications yet", "Check a message or enable automatic checks to see results here.")
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(bottom = 20.dp)) {
                items(state.predictions, key = { if (it.id > 0) it.id else it.hashCode().toLong() }) { prediction ->
                    HistoryCard(prediction)
                }
            }
        }
        if (!state.apiConnected.orFalse() && state.apiMessage != "Not checked yet") ErrorNotice(state.apiMessage)
    }
}

@Composable
private fun HistoryCard(prediction: Prediction) {
    val isSpam = prediction.prediction.equals("spam", ignoreCase = true)
    val accent = if (isSpam) GuardRed else GuardGreen
    Card(colors = CardDefaults.cardColors(containerColor = GuardSurface), shape = RoundedCornerShape(16.dp)) {
        Column(Modifier.fillMaxWidth().padding(15.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(if (isSpam) "SPAM" else "HAM", color = accent, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                Text("${(prediction.confidence * 100).toInt()}% · ${prediction.riskLevel}", color = GuardMuted, style = MaterialTheme.typography.labelMedium)
            }
            Text(prediction.message, maxLines = 3, overflow = TextOverflow.Ellipsis)
            Text(prediction.createdAt.ifBlank { "Time unavailable" }, color = GuardMuted, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun DashboardScreen(state: ScreenState, onRefresh: () -> Unit) {
    PageColumn {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Analytics", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                Text("Protection trends from the SpamGuard database", color = GuardMuted)
            }
            androidx.compose.material3.IconButton(onClick = onRefresh, enabled = !state.isRefreshing) {
                androidx.compose.material3.Icon(Icons.Default.Refresh, contentDescription = "Refresh dashboard")
            }
        }
        MetricCard("Total SMS checked", state.stats.totalMessages.toString(), Icons.Default.Mail)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MetricCard("Spam", state.stats.spamMessages.toString(), Icons.Default.Warning, Modifier.weight(1f), warning = true)
            MetricCard("Ham", state.stats.hamMessages.toString(), Icons.Default.CheckCircle, Modifier.weight(1f))
        }
        MetricCard("High-risk messages", state.stats.highRiskMessages.toString(), Icons.Default.Shield, warning = true)
        DistributionCard(state.stats)
        RiskSummaryCard(state.analytics.riskLevels)
        DailyDetectionsCard(state.analytics.daily)
        MetricCard(
            "Average confidence",
            String.format(Locale.getDefault(), "%.1f%%", state.analytics.averageConfidence * 100),
            Icons.Default.BarChart
        )
        ApiConnectionLine(state.apiConnected, state.apiMessage)
        if (state.apiConnected == false) ErrorNotice(state.apiMessage)
    }
}

@Composable
private fun RiskSummaryCard(riskLevels: Map<String, Int>) {
    Card(colors = CardDefaults.cardColors(containerColor = GuardSurface), shape = RoundedCornerShape(18.dp)) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Risk levels", fontWeight = FontWeight.SemiBold)
            DetailRow("High risk", (riskLevels["HIGH"] ?: 0).toString())
            DetailRow("Low risk", (riskLevels["LOW"] ?: 0).toString())
        }
    }
}

@Composable
private fun DailyDetectionsCard(daily: List<DailyAnalytics>) {
    val peak = daily.maxOfOrNull { it.total }?.coerceAtLeast(1) ?: 1
    Card(colors = CardDefaults.cardColors(containerColor = GuardSurface), shape = RoundedCornerShape(18.dp)) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Daily detections", fontWeight = FontWeight.SemiBold)
            if (daily.isEmpty()) {
                Text("No recent activity", color = GuardMuted, style = MaterialTheme.typography.bodySmall)
            } else {
                daily.takeLast(7).forEach { day ->
                    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(day.day, color = GuardMuted, style = MaterialTheme.typography.bodySmall)
                            Text("${day.total} total · ${day.spam} spam · ${day.ham} safe", style = MaterialTheme.typography.labelSmall)
                        }
                        LinearProgressIndicator(
                            progress = { day.total.toFloat() / peak },
                            modifier = Modifier.fillMaxWidth().height(6.dp),
                            color = GuardAccent,
                            trackColor = Color(0xFF344138)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DistributionCard(stats: DashboardStats) {
    val total = stats.spamMessages + stats.hamMessages
    val spamFraction = if (total > 0) stats.spamMessages.toFloat() / total else 0f
    Card(colors = CardDefaults.cardColors(containerColor = GuardSurface), shape = RoundedCornerShape(18.dp)) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Spam vs Ham", fontWeight = FontWeight.SemiBold)
            LinearProgressIndicator(
                progress = { spamFraction },
                modifier = Modifier.fillMaxWidth().height(9.dp),
                color = GuardRed,
                trackColor = GuardGreen
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Spam ${stats.spamMessages}", color = GuardRed, style = MaterialTheme.typography.bodySmall)
                Text("Ham ${stats.hamMessages}", color = GuardGreen, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun SettingsScreen(
    state: ScreenState,
    smsPermissionGranted: Boolean,
    automaticChecksEnabled: Boolean,
    notificationsEnabled: Boolean,
    onAutomaticChecksChanged: (Boolean) -> Unit,
    onNotificationsChanged: (Boolean) -> Unit,
    onRequestPermission: () -> Unit,
    onRefresh: () -> Unit
) {
    val context = LocalContext.current
    var apiUrlInput by remember { mutableStateOf(ProtectionPreferences.getApiBaseUrl(context)) }
    var simNumberInput by remember { mutableStateOf(ProtectionPreferences.getSimNumber(context)) }
    var settingsSavedMessage by remember { mutableStateOf<String?>(null) }

    PageColumn {
        PageHeading("Settings", "Control SMS access and the API connection.")

        Card(colors = CardDefaults.cardColors(containerColor = GuardSurface), shape = RoundedCornerShape(18.dp)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("SMS access", fontWeight = FontWeight.SemiBold)
                        Text(if (smsPermissionGranted) "Permission granted" else "Permission not granted", color = if (smsPermissionGranted) GuardGreen else GuardRed, style = MaterialTheme.typography.bodySmall)
                    }
                    if (!smsPermissionGranted) OutlinedButton(onClick = onRequestPermission) { Text("Grant") }
                }
                Text("SpamGuard only processes new incoming SMS while automatic checking is enabled. It does not read your inbox, send messages, or modify or delete SMS.", color = GuardMuted, style = MaterialTheme.typography.bodySmall)
                HorizontalDivider(color = Color(0xFF344138))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Automatic SMS checking", fontWeight = FontWeight.SemiBold)
                        Text("Send new incoming messages to the classifier immediately.", color = GuardMuted, style = MaterialTheme.typography.bodySmall)
                    }
                    Switch(checked = automaticChecksEnabled, onCheckedChange = onAutomaticChecksChanged)
                }
                HorizontalDivider(color = Color(0xFF344138))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Spam notifications", fontWeight = FontWeight.SemiBold)
                        Text("Alert when an incoming message is classified as spam.", color = GuardMuted, style = MaterialTheme.typography.bodySmall)
                    }
                    Switch(checked = notificationsEnabled, onCheckedChange = onNotificationsChanged)
                }
            }
        }

        Card(colors = CardDefaults.cardColors(containerColor = GuardSurface), shape = RoundedCornerShape(18.dp)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Test Phone SIM Number", fontWeight = FontWeight.SemiBold)
                Text("Matches your physical test SIM to link incoming SMS to your account.", color = GuardMuted, style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(
                    value = simNumberInput,
                    onValueChange = { simNumberInput = it },
                    label = { Text("SIM Number") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Button(
                    onClick = {
                        ProtectionPreferences.setSimNumber(context, simNumberInput)
                        settingsSavedMessage = "SIM number saved: ${simNumberInput.trim()}"
                        onRefresh()
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Save SIM Number")
                }
            }
        }

        Card(colors = CardDefaults.cardColors(containerColor = GuardSurface), shape = RoundedCornerShape(18.dp)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Backend API URL", modifier = Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                    Text(
                        when (state.apiConnected) {
                            true -> "Connected"
                            false -> "Unavailable"
                            null -> "Not checked"
                        },
                        color = if (state.apiConnected == true) GuardGreen else GuardMuted
                    )
                }
                Text("Enter the Flask backend server URL (must be reachable on this Wi-Fi network).", color = GuardMuted, style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(
                    value = apiUrlInput,
                    onValueChange = { apiUrlInput = it },
                    label = { Text("Flask Server URL") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    OutlinedButton(
                        onClick = {
                            val lanUrl = "http://192.168.1.107:5000/"
                            apiUrlInput = lanUrl
                            ProtectionPreferences.setApiBaseUrl(context, lanUrl)
                            settingsSavedMessage = "API URL set to LAN IP: $lanUrl"
                            onRefresh()
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Local LAN (192.168.1.107)")
                    }
                    Button(
                        onClick = {
                            ProtectionPreferences.setApiBaseUrl(context, apiUrlInput)
                            settingsSavedMessage = "API URL saved: ${apiUrlInput.trim()}"
                            onRefresh()
                        },
                        modifier = Modifier.weight(0.7f)
                    ) {
                        Text("Save")
                    }
                }
                OutlinedButton(onClick = onRefresh, enabled = !state.isRefreshing, modifier = Modifier.fillMaxWidth()) {
                    if (state.isRefreshing) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    else Text("Test connection")
                }
                if (settingsSavedMessage != null) {
                    Text(settingsSavedMessage!!, color = GuardGreen, style = MaterialTheme.typography.bodySmall)
                }
                if (state.apiConnected == false) ErrorNotice(state.apiMessage)
            }
        }
    }
}

@Composable
private fun MetricCard(
    title: String,
    value: String,
    icon: ImageVector,
    modifier: Modifier = Modifier,
    warning: Boolean = false
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = GuardSurface),
        shape = RoundedCornerShape(18.dp)
    ) {
        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Surface(shape = CircleShape, color = if (warning) Color(0xFF412823) else Color(0xFF263727), modifier = Modifier.size(40.dp)) {
                Box(contentAlignment = Alignment.Center) {
                    androidx.compose.material3.Icon(icon, contentDescription = null, tint = if (warning) GuardRed else GuardAccent, modifier = Modifier.size(20.dp))
                }
            }
            Column {
                Text(value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(title, color = GuardMuted, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = GuardMuted)
        Text(value, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun ApiConnectionLine(connected: Boolean?, message: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Surface(
            shape = CircleShape,
            color = when (connected) {
                true -> GuardGreen
                false -> GuardRed
                null -> GuardMuted
            },
            modifier = Modifier.size(8.dp)
        ) { }
        Text(message, color = GuardMuted, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun ErrorNotice(message: String) {
    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF38231F)), shape = RoundedCornerShape(12.dp)) {
        Text(message, modifier = Modifier.padding(14.dp), color = Color(0xFFFFB9A9), style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun EmptyState(title: String, message: String) {
    Box(Modifier.fillMaxSize().padding(30.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, fontWeight = FontWeight.SemiBold)
            Text(message, color = GuardMuted, style = MaterialTheme.typography.bodySmall)
        }
    }
}

private fun Boolean?.orFalse(): Boolean = this == true

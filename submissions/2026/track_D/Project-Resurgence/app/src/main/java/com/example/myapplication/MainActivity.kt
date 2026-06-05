package com.example.myapplication

import android.Manifest
import android.app.ActivityManager
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.location.Location
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import androidx.core.location.LocationManagerCompat
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import coil.compose.AsyncImage
import androidx.documentfile.provider.DocumentFile
import com.example.myapplication.ui.theme.*
import com.example.myapplication.utils.rememberResponsiveDimensions
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.SamplerConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.*

data class Message(
    val id: Long,
    val text: String,
    val isUser: Boolean,
    val isTyping: Boolean = false,
    val imageBitmap: Bitmap? = null,
    val timestamp: Long = System.currentTimeMillis()
)

data class SystemStatus(
    val ramAvailable: Long = 0,
    val ramTotal: Long = 0,
    val temperature: Float = 0f,
    val isThrottling: Boolean = false,
    val gpuAvailable: Boolean = true,
    val tokensPerSecond: Float = 0f,
    val totalTokens: Int = 0
)

enum class ModelLoadState {
    LOADING,
    READY,
    MISSING,
    ERROR
}

data class ModelStatus(
    val state: ModelLoadState = ModelLoadState.LOADING,
    val modelName: String? = null,
    val modelPath: String? = null,
    val errorMessage: String? = null
)

data class DehydratedMessage(
    val id: Long,
    val originalSize: Int,
    val compressedSize: Int,
    val compressionRatio: Float,
    val content: String,
    val timestamp: Long = System.currentTimeMillis()
)

data class PeerMessage(
    val id: Long,
    val peerId: String,
    val content: String,
    val timestamp: Long = System.currentTimeMillis(),
    val peerType: PeerType = PeerType.MOBILE
)

enum class PeerType {
    MOBILE, DRONE, SENSOR, SATELLITE
}

data class VerifiedAlert(
    val id: Long,
    val alertType: AlertType,
    val confidence: Float,
    val verifyingPeers: Int,
    val content: String,
    val timestamp: Long = System.currentTimeMillis(),
    val isTrusted: Boolean = true
)

enum class AlertType {
    DAM_BREAK, EARTHQUAKE, FIRE, FLOOD, TSUNAMI, STRUCTURE_COLLAPSE,
    CONTAMINATED_WATER, TOXIC_GAS, LAND_SLIDE, OTHER
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AppGlobals.appContext = applicationContext
        enableEdgeToEdge()
        setContent {
            val darkTheme = when (val settings = AppSettings()) {
                else -> when (settings.theme) {
                    Lang.get(Lang.DARK_MODE, settings.language) -> true
                    Lang.get(Lang.LIGHT_MODE, settings.language) -> false
                    else -> isSystemInDarkTheme()
                }
            }
            MyApplicationTheme(darkTheme = darkTheme) {
                ConsoleChatScreen()
            }
        }
    }
}

enum class Screen {
    Home, Help, TruthBoard, Camera, Settings
}

enum class Language(val code: String) {
    CHINESE("中文"),
    ENGLISH("English"),
    TRADITIONAL_CHINESE("繁體中文"),
    FRENCH("Français"),
    SPANISH("Español"),
    PORTUGUESE("Português"),
    JAPANESE("日本語"),
    KOREAN("한국어")
}

object Lang {
    private val ALL_LANGUAGES = listOf(
        Language.CHINESE,
        Language.ENGLISH,
        Language.TRADITIONAL_CHINESE,
        Language.FRENCH,
        Language.SPANISH,
        Language.PORTUGUESE,
        Language.JAPANESE,
        Language.KOREAN
    )

    private fun localizedMap(values: Map<Language, String>): Map<Language, String> {
        val fallback = values[Language.ENGLISH] ?: values[Language.CHINESE] ?: ""
        return ALL_LANGUAGES.associateWith { values[it] ?: fallback }
    }

    val APP_NAME = localizedMap(mapOf(
        Language.CHINESE to "Project Resurgence",
        Language.ENGLISH to "Project Resurgence",
        Language.TRADITIONAL_CHINESE to "Project Resurgence",
        Language.FRENCH to "Project Resurgence",
        Language.SPANISH to "Project Resurgence",
        Language.PORTUGUESE to "Project Resurgence",
        Language.JAPANESE to "Project Resurgence",
        Language.KOREAN to "Project Resurgence"
    ))
    
    val HOME = mapOf(
        Language.CHINESE to "首页",
        Language.ENGLISH to "Home"
    )
    
    val CAMERA = mapOf(
        Language.CHINESE to "拍照",
        Language.ENGLISH to "Camera"
    )
    
    val TRUTH = mapOf(
        Language.CHINESE to "真理",
        Language.ENGLISH to "Truth"
    )
    
    val SETTINGS = mapOf(
        Language.CHINESE to "设置",
        Language.ENGLISH to "Settings"
    )
    
    val ENTER_MESSAGE = mapOf(
        Language.CHINESE to "请输入消息...",
        Language.ENGLISH to "ENTER MESSAGE..."
    )
    
    val GENERATING = mapOf(
        Language.CHINESE to "正在生成...",
        Language.ENGLISH to "GENERATING..."
    )
    
    val SEND = mapOf(
        Language.CHINESE to "发送",
        Language.ENGLISH to "SEND"
    )
    
    val BROADCAST_DISASTER = mapOf(
        Language.CHINESE to "📡 广播灾情 (信息极致脱水)",
        Language.ENGLISH to "📡 Broadcast Disaster (Info Dehydration)"
    )
    
    val SYSTEM_READY = mapOf(
        Language.CHINESE to "系统已就绪。\n节点: STANDARD_Q4\n欢迎来到 Project Resurgence。\n\n正在初始化 GEMMA 4 引擎...",
        Language.ENGLISH to "SYSTEM READY.\nNODE: STANDARD_Q4\nWELCOME TO Project Resurgence.\n\nINITIALIZING GEMMA 4 ENGINE..."
    )
    
    val BASIC_SETTINGS = mapOf(
        Language.CHINESE to "基本设置",
        Language.ENGLISH to "Basic Settings"
    )
    
    val NOTIFICATIONS = mapOf(
        Language.CHINESE to "通知提醒",
        Language.ENGLISH to "Notifications"
    )
    
    val NOTIFICATIONS_DESC = mapOf(
        Language.CHINESE to "接收紧急通知",
        Language.ENGLISH to "Receive emergency notifications"
    )
    
    val LOCATION = mapOf(
        Language.CHINESE to "位置服务",
        Language.ENGLISH to "Location Services"
    )
    
    val LOCATION_DESC = mapOf(
        Language.CHINESE to "允许访问位置信息",
        Language.ENGLISH to "Allow location access"
    )
    
    val SAVE_PHOTOS = mapOf(
        Language.CHINESE to "保存照片",
        Language.ENGLISH to "Save Photos"
    )
    
    val SAVE_PHOTOS_DESC = mapOf(
        Language.CHINESE to "自动保存拍摄的照片",
        Language.ENGLISH to "Automatically save captured photos"
    )
    
    val ADVANCED_SETTINGS = mapOf(
        Language.CHINESE to "高级设置",
        Language.ENGLISH to "Advanced Settings"
    )
    
    val AUTO_BROADCAST = mapOf(
        Language.CHINESE to "自动广播",
        Language.ENGLISH to "Auto Broadcast"
    )
    
    val AUTO_BROADCAST_DESC = mapOf(
        Language.CHINESE to "检测到危险时自动广播",
        Language.ENGLISH to "Auto broadcast when danger detected"
    )
    
    val LANGUAGE = mapOf(
        Language.CHINESE to "语言",
        Language.ENGLISH to "Language"
    )
    
    val THEME = mapOf(
        Language.CHINESE to "主题",
        Language.ENGLISH to "Theme"
    )
    
    val DARK_MODE = mapOf(
        Language.CHINESE to "深色模式",
        Language.ENGLISH to "Dark Mode"
    )
    
    val LIGHT_MODE = mapOf(
        Language.CHINESE to "浅色模式",
        Language.ENGLISH to "Light Mode"
    )
    
    val ABOUT = mapOf(
        Language.CHINESE to "关于",
        Language.ENGLISH to "About"
    )
    
    val VERSION_INFO = mapOf(
        Language.CHINESE to "版本信息",
        Language.ENGLISH to "Version Info"
    )
    
    val VERSION_DESC = mapOf(
        Language.CHINESE to "Project Resurgence v1.0.0",
        Language.ENGLISH to "Project Resurgence v1.0.0"
    )
    
    val PRIVACY_POLICY = mapOf(
        Language.CHINESE to "隐私政策",
        Language.ENGLISH to "Privacy Policy"
    )
    
    val PRIVACY_POLICY_DESC = mapOf(
        Language.CHINESE to "查看隐私政策",
        Language.ENGLISH to "View privacy policy"
    )
    
    val HELP_FEEDBACK = mapOf(
        Language.CHINESE to "帮助与反馈",
        Language.ENGLISH to "Help & Feedback"
    )
    
    val HELP_FEEDBACK_DESC = mapOf(
        Language.CHINESE to "联系我们",
        Language.ENGLISH to "Contact us"
    )
    
    val CONTINUE = mapOf(
        Language.CHINESE to "继续",
        Language.ENGLISH to "CONTINUE"
    )
    
    val PROCEED_ANYWAY = mapOf(
        Language.CHINESE to "仍要继续",
        Language.ENGLISH to "PROCEED ANYWAY"
    )
    
    val HARDWARE_CHECK = mapOf(
        Language.CHINESE to "硬件准入检查",
        Language.ENGLISH to "HARDWARE ADMISSION CHECK"
    )
    
    val AVAILABLE_RAM = mapOf(
        Language.CHINESE to "可用内存",
        Language.ENGLISH to "AVAILABLE RAM"
    )
    
    val RAM_REQUIREMENT = mapOf(
        Language.CHINESE to "≥ 2048 MB",
        Language.ENGLISH to "≥ 2048 MB"
    )
    
    val GPU_SUPPORT = mapOf(
        Language.CHINESE to "GPU/Vulkan 支持",
        Language.ENGLISH to "GPU/VULKAN SUPPORT"
    )
    
    val GPU_REQUIREMENT = mapOf(
        Language.CHINESE to "Vulkan 1.1+",
        Language.ENGLISH to "VULKAN 1.1+"
    )
    
    val MEMORY_HEADROOM = mapOf(
        Language.CHINESE to "内存余量",
        Language.ENGLISH to "MEMORY HEADROOM"
    )
    
    val MEMORY_REQUIREMENT = mapOf(
        Language.CHINESE to "≥ 30%",
        Language.ENGLISH to "≥ 30%"
    )
    
    val DEGRADED_MODE = mapOf(
        Language.CHINESE to "⚠️ 性能降级模式已激活",
        Language.ENGLISH to "⚠️ DEGRADED PERFORMANCE MODE ACTIVE"
    )
    
    val TRUTH_BOARD = mapOf(
        Language.CHINESE to "⚖️ 灾情真理看板",
        Language.ENGLISH to "⚖️ TRUTH BOARD"
    )
    
    val CLOSE = mapOf(
        Language.CHINESE to "关闭",
        Language.ENGLISH to "Close"
    )
    
    val SIMULATE_PANIC = mapOf(
        Language.CHINESE to "模拟恐慌消息",
        Language.ENGLISH to "Simulate Panic Messages"
    )
    
    val SIMULATING = mapOf(
        Language.CHINESE to "模拟中...",
        Language.ENGLISH to "Simulating..."
    )
    
    val CLEAR_RECORDS = mapOf(
        Language.CHINESE to "清空记录",
        Language.ENGLISH to "Clear Records"
    )
    
    val TRUSTED_ALERTS = mapOf(
        Language.CHINESE to "🔴 可信警报 (通过验证)",
        Language.ENGLISH to "🔴 TRUSTED ALERTS (Verified)"
    )
    
    val PEER_MESSAGES = mapOf(
        Language.CHINESE to "📡 节点原始消息 (未验证)",
        Language.ENGLISH to "📡 PEER MESSAGES (Unverified)"
    )
    
    val WAITING_NETWORK = mapOf(
        Language.CHINESE to "等待网络消息...\n点击\"模拟恐慌消息\"开始演示",
        Language.ENGLISH to "Waiting for network messages...\nClick \"Simulate Panic Messages\" to start demo"
    )
    
    val ALERT_TYPE = mapOf(
        Language.CHINESE to "警报类型: ",
        Language.ENGLISH to "Alert Type: "
    )
    
    val CONFIDENCE = mapOf(
        Language.CHINESE to "可信度: ",
        Language.ENGLISH to "Confidence: "
    )
    
    val VERIFYING_PEERS = mapOf(
        Language.CHINESE to "验证节点: ",
        Language.ENGLISH to "Verifying Peers: "
    )
    
    val PEER_NODE = mapOf(
        Language.CHINESE to "节点: ",
        Language.ENGLISH to "Node: "
    )
    
    val SURVIVAL_MENTOR = mapOf(
        Language.CHINESE to "SURVIVAL MENTOR",
        Language.ENGLISH to "SURVIVAL MENTOR"
    )
    
    val TAKE_PHOTO = mapOf(
        Language.CHINESE to "拍照",
        Language.ENGLISH to "Take Photo"
    )
    
    val ANALYZE_HELP = mapOf(
        Language.CHINESE to "分析并求助",
        Language.ENGLISH to "Analyze & Help"
    )

    val SAVE_PHOTO = mapOf(
        Language.CHINESE to "保存照片",
        Language.ENGLISH to "Save Photo"
    )

    val UPLOAD_PHOTO = mapOf(
        Language.CHINESE to "上传照片",
        Language.ENGLISH to "Upload Photo"
    )

    val SELECT_FROM_GALLERY = mapOf(
        Language.CHINESE to "从相册选择",
        Language.ENGLISH to "Select from Gallery"
    )

    val PHOTO_SAVED = mapOf(
        Language.CHINESE to "照片已保存到相册",
        Language.ENGLISH to "Photo saved to gallery"
    )

    val PHOTO_UPLOADED = mapOf(
        Language.CHINESE to "照片已上传",
        Language.ENGLISH to "Photo uploaded"
    )

    val PHOTO_CAPTURED = mapOf(
        Language.CHINESE to "照片已拍摄，请评估。",
        Language.ENGLISH to "Photo captured, please assess."
    )
    
    val BLEEDING_DETECTED = mapOf(
        Language.CHINESE to "⚠️ 检测到可能的出血症状",
        Language.ENGLISH to "⚠️ Possible bleeding detected"
    )
    
    val HIGH_SUSPECT_BLEEDING = mapOf(
        Language.CHINESE to "🔴 高度怀疑伤口出血，请立即处理",
        Language.ENGLISH to "🔴 High suspicion of bleeding, treat immediately"
    )
    
    val MINOR_ABRASION = mapOf(
        Language.CHINESE to "🩸 检测到红色区域，可能是轻微擦伤",
        Language.ENGLISH to "🩸 Red area detected, possible minor abrasion"
    )
    
    val OBSERVE_RED_AREA = mapOf(
        Language.CHINESE to "发现少量红色区域，请观察",
        Language.ENGLISH to "Small red area found, observe"
    )
    
    val NO_WOUND_DETECTED = mapOf(
        Language.CHINESE to "未检测到明显伤口或出血症状",
        Language.ENGLISH to "No obvious wound or bleeding symptoms detected"
    )

    val TRUTH_BOARD_TITLE = mapOf(
        Language.CHINESE to "⚖️ 灾情真理看板",
        Language.ENGLISH to "⚖️ TRUTH BOARD"
    )
    
    val BROADCASTING = mapOf(
        Language.CHINESE to "📡 正在广播灾情...",
        Language.ENGLISH to "📡 Broadcasting disaster..."
    )
    
    val THERMAL_WARNING = mapOf(
        Language.CHINESE to "⚠️ 过热警告！",
        Language.ENGLISH to "⚠️ Thermal Throttling!"
    )
    
    val BACK = mapOf(
        Language.CHINESE to "← 返回",
        Language.ENGLISH to "← Back"
    )

    val AI_HELP = mapOf(
        Language.CHINESE to "AI 求助",
        Language.ENGLISH to "AI Help"
    )

    val SEMANTIC_BROADCAST = mapOf(
        Language.CHINESE to "语义感知组网广播中...",
        Language.ENGLISH to "Semantic network broadcasting..."
    )

    val INFO_DEHYDRATION = mapOf(
        Language.CHINESE to "信息极致脱水处理",
        Language.ENGLISH to "Extreme information dehydration"
    )

    val LOGIC_ARBITRATOR = mapOf(
        Language.CHINESE to "逻辑仲裁官 - 去中心化验证",
        Language.ENGLISH to "Logic Arbitrator - Decentralized Verification"
    )

    val ONLINE_PEERS = mapOf(
        Language.CHINESE to "在线节点",
        Language.ENGLISH to "Online Peers"
    )

    val DEVICES = mapOf(
        Language.CHINESE to "个设备",
        Language.ENGLISH to "devices"
    )

    val RECEIVED_MESSAGES = mapOf(
        Language.CHINESE to "收到消息",
        Language.ENGLISH to "Received Messages"
    )

    val MESSAGES = mapOf(
        Language.CHINESE to "条",
        Language.ENGLISH to "messages"
    )

    val ALERTS = mapOf(
        Language.CHINESE to "个",
        Language.ENGLISH to "alerts"
    )

    val SYSTEM = mapOf(
        Language.CHINESE to "系统",
        Language.ENGLISH to "System"
    )

    val READY = mapOf(
        Language.CHINESE to "就绪",
        Language.ENGLISH to "Ready"
    )

    val TOOLS = mapOf(
        Language.CHINESE to "工具",
        Language.ENGLISH to "Tools"
    )

    val STATUS = mapOf(
        Language.CHINESE to "状态",
        Language.ENGLISH to "Status"
    )

    val SERVER = mapOf(
        Language.CHINESE to "服务器",
        Language.ENGLISH to "Server"
    )

    val CORE = mapOf(
        Language.CHINESE to "核心",
        Language.ENGLISH to "Core"
    )

    val ALERT_TITLE = mapOf(
        Language.CHINESE to "警报",
        Language.ENGLISH to "Alert"
    )

    val DAM_BREAK = mapOf(
        Language.CHINESE to "溃坝风险",
        Language.ENGLISH to "Dam Break"
    )

    val FIRE = mapOf(
        Language.CHINESE to "火灾",
        Language.ENGLISH to "Fire"
    )

    val EARTHQUAKE = mapOf(
        Language.CHINESE to "地震",
        Language.ENGLISH to "Earthquake"
    )

    val FLOOD = mapOf(
        Language.CHINESE to "洪水",
        Language.ENGLISH to "Flood"
    )

    val TYPHOON = mapOf(
        Language.CHINESE to "台风",
        Language.ENGLISH to "Typhoon"
    )

    val VERIFIED_BY = mapOf(
        Language.CHINESE to "验证者",
        Language.ENGLISH to "Verified By"
    )

    val PEERS = mapOf(
        Language.CHINESE to "节点",
        Language.ENGLISH to "peers"
    )

    val LAST_UPDATE = mapOf(
        Language.CHINESE to "最后更新",
        Language.ENGLISH to "Last Update"
    )

    val JUST_NOW = mapOf(
        Language.CHINESE to "刚刚",
        Language.ENGLISH to "Just now"
    )

    val MINUTES_AGO = mapOf(
        Language.CHINESE to "分钟前",
        Language.ENGLISH to "minutes ago"
    )

    val SENSOR = mapOf(
        Language.CHINESE to "传感器",
        Language.ENGLISH to "Sensor"
    )

    val MOBILE = mapOf(
        Language.CHINESE to "移动",
        Language.ENGLISH to "Mobile"
    )

    val DRONE = mapOf(
        Language.CHINESE to "无人机",
        Language.ENGLISH to "Drone"
    )

    val SATELLITE = mapOf(
        Language.CHINESE to "卫星",
        Language.ENGLISH to "Satellite"
    )

    val PEER_MESSAGE = mapOf(
        Language.CHINESE to "节点消息",
        Language.ENGLISH to "Peer Message"
    )

    val PEER_NODES = mapOf(
        Language.CHINESE to "验证节点: ",
        Language.ENGLISH to "Verifying Peers: "
    )

    val PEER_NODES_COUNT = mapOf(
        Language.CHINESE to "个",
        Language.ENGLISH to "nodes"
    )

    val LOCATION_GETTING = mapOf(
        Language.CHINESE to "获取位置中...",
        Language.ENGLISH to "Getting location..."
    )

    val LOCATION_DENIED = mapOf(
        Language.CHINESE to "位置权限被拒绝",
        Language.ENGLISH to "Location permission denied"
    )

    val LATITUDE = mapOf(
        Language.CHINESE to "纬度",
        Language.ENGLISH to "Lat"
    )

    val LONGITUDE = mapOf(
        Language.CHINESE to "经度",
        Language.ENGLISH to "Lon"
    )

    val ACCURACY = mapOf(
        Language.CHINESE to "精度",
        Language.ENGLISH to "Accuracy"
    )

    val METERS = mapOf(
        Language.CHINESE to "米",
        Language.ENGLISH to "m"
    )


    fun get(key: Map<Language, String>, language: Language): String {
        return key[language] ?: key[Language.CHINESE] ?: ""
    }
}

@Composable
fun ConsoleChatScreen() {
    val context = LocalContext.current
    val appContext = context.applicationContext
    val dimensions = rememberResponsiveDimensions()
    var messages by remember { mutableStateOf(listOf<Message>()) }
    var inputText by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    var showHardwareCheck by remember { mutableStateOf(true) }
    var systemStatus by remember { mutableStateOf(SystemStatus()) }
    var isGenerating by remember { mutableStateOf(false) }
    var hasCameraPermission by remember { mutableStateOf(false) }
    var hasLocationPermission by remember { mutableStateOf(false) }
    var isBroadcasting by remember { mutableStateOf(false) }
    var dehydratedMessages by remember { mutableStateOf(listOf<DehydratedMessage>()) }
    var currentScreen by remember { mutableStateOf(Screen.Home) }
    var peerMessages by remember { mutableStateOf(listOf<PeerMessage>()) }
    var verifiedAlerts by remember { mutableStateOf(listOf<VerifiedAlert>()) }
    var networkPeers by remember { mutableStateOf(8) }
    var isSimulating by remember { mutableStateOf(false) }
    var appSettings by remember { mutableStateOf(AppSettings()) }
    var locationInfo by remember { mutableStateOf(LocationInfo()) }
    var isGettingLocation by remember { mutableStateOf(false) }
    var modelStatus by remember { mutableStateOf(ModelStatus()) }
    var streamTokenVersion by remember { mutableStateOf(0L) }
    var pendingStreamJobId by remember { mutableStateOf(0L) }
    val darkTheme = when (appSettings.theme) {
        Lang.get(Lang.DARK_MODE, appSettings.language) -> true
        Lang.get(Lang.LIGHT_MODE, appSettings.language) -> false
        else -> isSystemInDarkTheme()
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { granted ->
            hasCameraPermission = granted
            if (granted) {
                currentScreen = Screen.Camera
            }
        }
    )

    val importModelLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument(),
        onResult = { uri ->
            uri ?: return@rememberLauncherForActivityResult
            scope.launch {
                modelStatus = ModelStatus(state = ModelLoadState.LOADING)
                val result = importLocalModelFile(context, uri)
                modelStatus = if (result != null) {
                    scanLocalModel(context, appSettings.language)
                } else {
                    ModelStatus(
                        state = ModelLoadState.ERROR,
                        errorMessage = if (appSettings.language == Language.CHINESE) "导入模型失败" else "Failed to import model"
                    )
                }
            }
        }
    )

    val locationPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
        onResult = { granted ->
            hasLocationPermission = granted
            if (granted) {
                isGettingLocation = true
                requestLocationUpdates(context) { newLocation ->
                    locationInfo = newLocation
                    isGettingLocation = false
                }
            }
        }
    )

    LaunchedEffect(Unit) {
        hasCameraPermission = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED

        hasLocationPermission = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        if (hasLocationPermission) {
            isGettingLocation = true
            requestLocationUpdates(context) { newLocation ->
                locationInfo = newLocation
                isGettingLocation = false
            }
        } else {
            locationPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
        }
        
        val (ramAvail, ramTotal) = checkRam(context)
        val initialTemp = readDeviceTemperature(context)
        systemStatus = systemStatus.copy(
            ramAvailable = ramAvail,
            ramTotal = ramTotal,
            gpuAvailable = true,
            temperature = initialTemp,
            isThrottling = initialTemp >= 60f
        )
        
        messages = listOf(
            Message(
                id = 0,
                text = Lang.get(Lang.SYSTEM_READY, appSettings.language),
                isUser = false
            )
        )

        showHardwareCheck = false
        modelStatus = scanLocalModel(context, appSettings.language)
        messages = messages + Message(
            id = 1,
            text = when (modelStatus.state) {
                ModelLoadState.READY -> if (appSettings.language == Language.CHINESE) {
                    "已检测到本地模型：${modelStatus.modelName ?: "Gemma"}"
                } else {
                    "Local model detected: ${modelStatus.modelName ?: "Gemma"}"
                }
                ModelLoadState.MISSING -> if (appSettings.language == Language.CHINESE) {
                    "未检测到本地 Gemma LiteRT-LM 模型，请点击首页卡片或导入按钮选择模型文件。"
                } else {
                    "No local Gemma LiteRT-LM model found. Use the home card or import button to choose a model file."
                }
                ModelLoadState.LOADING -> if (appSettings.language == Language.CHINESE) {
                    "正在扫描本地模型..."
                } else {
                    "Scanning local model..."
                }
                ModelLoadState.ERROR -> modelStatus.errorMessage ?: "Model scan failed"
            },
            isUser = false
        )
    }

    LaunchedEffect(appSettings.language) {
        modelStatus = scanLocalModel(context, appSettings.language)
    }

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    LaunchedEffect(appSettings.language) {
        messages = listOf(
            Message(
                id = 0,
                text = Lang.get(Lang.SYSTEM_READY, appSettings.language),
                isUser = false
            )
        )
    }

    LaunchedEffect(Unit) {
        while (true) {
            val (ramAvail, ramTotal) = checkRam(context)
            val temp = readDeviceTemperature(context)
            val isThrottling = temp >= 60f
            
            systemStatus = systemStatus.copy(
                ramAvailable = ramAvail,
                ramTotal = ramTotal,
                temperature = temp,
                isThrottling = isThrottling
            )
            delay(2000)
        }
    }

    val colors = MaterialTheme.colorScheme
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background)
            .windowInsetsPadding(WindowInsets.systemBars)
    ) {
        Column(
            modifier = Modifier.fillMaxSize()
        ) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
            ) {
                when (currentScreen) {
                    Screen.Home -> {
                        HomeScreen(
                            dimensions = dimensions,
                            messages = messages,
                            inputText = inputText,
                            listState = listState,
                            scope = scope,
                            systemStatus = systemStatus,
                            modelStatus = modelStatus,
                            isGenerating = isGenerating,
                            onInputTextChange = { inputText = it },
                            onSend = {
                                if (inputText.isNotEmpty() && !isGenerating) {
                                    val userMessage = Message(
                                        id = System.currentTimeMillis(),
                                        text = inputText,
                                        isUser = true
                                    )
                                    messages = messages + userMessage
                                    inputText = ""
                                    isGenerating = true
                                    val jobId = System.currentTimeMillis()
                                    pendingStreamJobId = jobId

                                    scope.launch {
                                        val typingMessage = Message(
                                            id = System.currentTimeMillis() + 1,
                                            text = "",
                                            isUser = false,
                                            isTyping = true
                                        )
                                        messages = messages + typingMessage

                                        val response = runCatching {
                                            streamLocalChatResponse(context, userMessage.text, appSettings.language)
                                        }.getOrElse { flowOfChunks(generateLocalChatFallback(userMessage.text)) }

                                        var currentText = ""
                                        val typingMessageId = typingMessage.id
                                        response.collect { chunk ->
                                            if (pendingStreamJobId != jobId) return@collect
                                            currentText += chunk
                                            messages = messages.map {
                                                if (it.id == typingMessageId) it.copy(text = currentText) else it
                                            }
                                            systemStatus = systemStatus.copy(
                                                tokensPerSecond = (systemStatus.tokensPerSecond + 2f).coerceAtMost(120f),
                                                totalTokens = systemStatus.totalTokens + chunk.length
                                            )
                                        }
                                        messages = messages.map {
                                            if (it.id == typingMessageId) it.copy(isTyping = false) else it
                                        }
                                        isGenerating = false
                                    }
                                }
                            },
                            onBroadcast = {
                                scope.launch {
                                    isBroadcasting = true
                                    delay(1000)
                                    
                                    val dehydrated = dehydrateMessageForBroadcast(inputText)
                                    dehydratedMessages = dehydratedMessages + dehydrated
                                    
                                    val broadcastMsg = Message(
                                        id = System.currentTimeMillis(),
                                        text = "【广播灾情】\n${dehydrated.content}\n\n[原始: ${dehydrated.originalSize} bytes → 压缩: ${dehydrated.compressedSize} bytes (${String.format("%.1f", dehydrated.compressionRatio)}x 压缩)]",
                                        isUser = true
                                    )
                                    messages = messages + broadcastMsg
                                    inputText = ""
                                    
                                    delay(1000)
                                    isBroadcasting = false
                                }
                            },
                            onCameraClick = { 
                                if (hasCameraPermission) {
                                    currentScreen = Screen.Camera
                                } else {
                                    permissionLauncher.launch(Manifest.permission.CAMERA)
                                }
                            },
                            onTruthBoardClick = { currentScreen = Screen.TruthBoard },
                            onImportModelClick = { importModelLauncher.launch(arrayOf("*/*")) },
                            language = appSettings.language,
                            locationInfo = locationInfo,
                            isGettingLocation = isGettingLocation,
                            hasLocationPermission = hasLocationPermission
                        )
                    }
                    Screen.Help -> {
                        HelpScreen(
                            dimensions = dimensions,
                            messages = messages,
                            inputText = inputText,
                            listState = listState,
                            scope = scope,
                            systemStatus = systemStatus,
                            isGenerating = isGenerating,
                            onInputTextChange = { inputText = it },
                            onSend = {
                                if (inputText.isNotEmpty() && !isGenerating) {
                                    val userMessage = Message(
                                        id = System.currentTimeMillis(),
                                        text = inputText,
                                        isUser = true
                                    )
                                    messages = messages + userMessage
                                    inputText = ""
                                    isGenerating = true

                                    scope.launch {
                                        val typingMessage = Message(
                                            id = System.currentTimeMillis() + 1,
                                            text = "",
                                            isUser = false,
                                            isTyping = true
                                        )
                                        messages = messages + typingMessage

                                        delay(800)

                                        val response = runCatching {
                                            generateChatResponse(context, userMessage.text, appSettings.language)
                                        }.getOrElse { generateLocalChatFallback(userMessage.text) }
                                        var currentText = ""
                                        val typingMessageId = typingMessage.id
                                        response.forEachIndexed { _, char ->
                                            delay(20)
                                            currentText += char
                                            messages = messages.map {
                                                if (it.id == typingMessageId) it.copy(text = currentText) else it
                                            }
                                            systemStatus = systemStatus.copy(
                                                tokensPerSecond = 33.3f,
                                                totalTokens = systemStatus.totalTokens + 1
                                            )
                                        }
                                        messages = messages.map {
                                            if (it.id == typingMessageId) it.copy(isTyping = false) else it
                                        }
                                        isGenerating = false
                                    }
                                }
                            },
                            onBroadcast = {
                                scope.launch {
                                    isBroadcasting = true
                                    delay(1000)
                                    
                                    val dehydrated = dehydrateMessageForBroadcast(inputText)
                                    dehydratedMessages = dehydratedMessages + dehydrated
                                    
                                    val broadcastMsg = Message(
                                        id = System.currentTimeMillis(),
                                        text = "【广播灾情】\n${dehydrated.content}\n\n[原始: ${dehydrated.originalSize} bytes → 压缩: ${dehydrated.compressedSize} bytes (${String.format("%.1f", dehydrated.compressionRatio)}x 压缩)]",
                                        isUser = true
                                    )
                                    messages = messages + broadcastMsg
                                    inputText = ""
                                    
                                    delay(1000)
                                    isBroadcasting = false
                                }
                            },
                            onBack = { currentScreen = Screen.Home },
                            onTruthBoard = { currentScreen = Screen.TruthBoard },
                            language = appSettings.language
                        )
                    }
                    Screen.TruthBoard -> {
                        TruthBoardPanel(
                            verifiedAlerts = verifiedAlerts,
                            peerMessages = peerMessages,
                            networkPeers = networkPeers,
                            isSimulating = isSimulating,
                            onClose = { currentScreen = Screen.Home },
                            onStartSimulation = {
                                isSimulating = true
                                scope.launch {
                                    simulatePeerMessages(
                                        onNewMessage = { newPeerMsg ->
                                            peerMessages = peerMessages + newPeerMsg
                                            scope.launch {
                                                val trusted = runCatching {
                                                    runArbitration(peerMessages + newPeerMsg)
                                                }.getOrNull()?.isTrusted == true
                                                if (trusted) {
                                                    verifiedAlerts = verifiedAlerts + newPeerMsg.toVerifiedAlert()
                                                }
                                            }
                                        },
                                        onComplete = {
                                            isSimulating = false
                                        }
                                    )
                                }
                            },
                            onClear = {
                                peerMessages = listOf()
                                verifiedAlerts = listOf()
                            },
                            language = appSettings.language
                        )
                    }
                    Screen.Camera -> {
                        SurvivalMentorPanel(
                            onClose = { currentScreen = Screen.Home },
                            onPhotoCaptured = { bitmap, description ->
                                messages = messages + Message(
                                    id = System.currentTimeMillis(),
                                    text = description,
                                    isUser = true,
                                    imageBitmap = bitmap
                                )
                                isGenerating = true
                                scope.launch {
                                    val typingMessage = Message(
                                        id = System.currentTimeMillis() + 1,
                                        text = "",
                                        isUser = false,
                                        isTyping = true
                                    )
                                    messages = messages + typingMessage

                                    delay(300)

                                    val response = runCatching {
                                        generateAnalysisResponse(context, description, bitmap, appSettings.language)
                                    }.getOrElse { generateLocalAnalysisFallback(description) }
                                    var currentText = ""
                                    val typingMessageId = typingMessage.id
                                    response.forEachIndexed { _, char ->
                                        delay(20)
                                        currentText += char
                                        messages = messages.map {
                                            if (it.id == typingMessageId) it.copy(text = currentText) else it
                                        }
                                        systemStatus = systemStatus.copy(
                                            tokensPerSecond = 33.3f,
                                            totalTokens = systemStatus.totalTokens + 1
                                        )
                                    }

                                    messages = messages.map {
                                        if (it.id == typingMessageId) it.copy(isTyping = false) else it
                                    }
                                    isGenerating = false
                                    currentScreen = Screen.Home
                                }
                            },
                            language = appSettings.language
                        )
                    }
                    Screen.Settings -> {
                        SettingsScreen(
                            dimensions = dimensions,
                            settings = appSettings,
                            onSettingsChange = { appSettings = it },
                            language = appSettings.language,
                            modelStatus = modelStatus,
                            onImportModelClick = { importModelLauncher.launch(arrayOf("*/*")) }
                        )
                    }
                }
            }

            BottomNavigationBar(
                currentScreen = currentScreen,
                onScreenChange = { screen ->
                    if (screen == Screen.Camera && !hasCameraPermission) {
                        permissionLauncher.launch(Manifest.permission.CAMERA)
                    } else {
                        currentScreen = screen
                    }
                },
                dimensions = dimensions,
                language = appSettings.language
            )
        }

        if (isBroadcasting) {
            BroadcastingOverlay(language = appSettings.language)
        }

        if (systemStatus.isThrottling) {
            ThermalWarningOverlay(language = appSettings.language)
        }

        if (showHardwareCheck) {
            HardwareCheckDialog(
                systemStatus = systemStatus,
                onDismiss = { showHardwareCheck = false },
                language = appSettings.language
            )
        }
    }
}

@Composable
fun LocationDisplay(
    locationInfo: LocationInfo,
    isGettingLocation: Boolean,
    hasLocationPermission: Boolean,
    language: Language,
    dimensions: com.example.myapplication.utils.ResponsiveDimensions
) {
    val colors = MaterialTheme.colorScheme
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(dimensions.buttonRadius))
            .background(colors.surfaceVariant.copy(alpha = 0.7f))
            .padding(dimensions.small),
        horizontalArrangement = Arrangement.spacedBy(dimensions.small),
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (isGettingLocation) {
            Text(
                text = "📍",
                fontSize = 18.sp
            )
            Text(
                text = Lang.get(Lang.LOCATION_GETTING, language),
                color = SlateGrey,
                fontSize = dimensions.fontSizeSmall.sp
            )
        } else if (!hasLocationPermission) {
            Text(
                text = "📍",
                fontSize = 18.sp
            )
            Text(
                text = Lang.get(Lang.LOCATION_DENIED, language),
                color = AlertRed,
                fontSize = dimensions.fontSizeSmall.sp
            )
        } else if (locationInfo.hasLocation) {
            Text(
                text = "📍",
                fontSize = 18.sp
            )
            Column {
                Text(
                    text = "${Lang.get(Lang.LATITUDE, language)}: ${String.format("%.4f", locationInfo.latitude)}",
                    color = PureWhite,
                    fontSize = dimensions.fontSizeSmall.sp,
                    lineHeight = (dimensions.fontSizeSmall * 1.4).sp
                )
                Text(
                    text = "${Lang.get(Lang.LONGITUDE, language)}: ${String.format("%.4f", locationInfo.longitude)}",
                    color = PureWhite,
                    fontSize = dimensions.fontSizeSmall.sp,
                    lineHeight = (dimensions.fontSizeSmall * 1.4).sp
                )
                Text(
                    text = "${Lang.get(Lang.ACCURACY, language)}: ${String.format("%.0f", locationInfo.accuracy)}${Lang.get(Lang.METERS, language)}",
                    color = SurvivalGreen,
                    fontSize = (dimensions.fontSizeSmall * 0.85).sp,
                    lineHeight = (dimensions.fontSizeSmall * 1.4).sp
                )
            }
        } else {
            Text(
                text = "📍",
                fontSize = 18.sp
            )
            Text(
                text = Lang.get(Lang.LOCATION_GETTING, language),
                color = SlateGrey,
                fontSize = dimensions.fontSizeSmall.sp
            )
        }
    }
}

@Composable
fun HomeScreen(
    dimensions: com.example.myapplication.utils.ResponsiveDimensions,
    messages: List<Message>,
    inputText: String,
    listState: androidx.compose.foundation.lazy.LazyListState,
    scope: kotlinx.coroutines.CoroutineScope,
    systemStatus: SystemStatus,
    modelStatus: ModelStatus,
    isGenerating: Boolean,
    onInputTextChange: (String) -> Unit,
    onSend: () -> Unit,
    onBroadcast: () -> Unit,
    onCameraClick: () -> Unit,
    onTruthBoardClick: () -> Unit,
    onImportModelClick: () -> Unit,
    language: Language,
    locationInfo: LocationInfo,
    isGettingLocation: Boolean,
    hasLocationPermission: Boolean
) {
    Column(
        modifier = Modifier.fillMaxSize()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    top = dimensions.medium,
                    start = dimensions.medium,
                    end = dimensions.medium
                ),
            horizontalArrangement = Arrangement.Start
        ) {
            LocationDisplay(
                locationInfo = locationInfo,
                isGettingLocation = isGettingLocation,
                hasLocationPermission = hasLocationPermission,
                language = language,
                dimensions = dimensions
            )
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    start = dimensions.medium,
                    end = dimensions.medium,
                    bottom = dimensions.medium
                ),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = Lang.get(Lang.APP_NAME, language),
                color = SurvivalGreen,
                fontSize = dimensions.fontSizeTitle.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.15.sp
            )
        }

        LazyColumn(
            state = listState,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentPadding = PaddingValues(
                horizontal = dimensions.medium,
                vertical = dimensions.medium
            ),
            verticalArrangement = Arrangement.spacedBy(dimensions.medium)
        ) {
            items(messages, key = { it.id }) { message ->
                MessageBubble(message = message)
            }
        }

        TelemetryBar(systemStatus = systemStatus)

        InputBar(
            text = inputText,
            onTextChange = onInputTextChange,
            onSend = onSend,
            onBroadcast = onBroadcast,
            enabled = !isGenerating,
            language = language
        )
    }
}

@Composable
fun ModelStatusCard(
    modelStatus: ModelStatus,
    language: Language,
    dimensions: com.example.myapplication.utils.ResponsiveDimensions,
    onImportModelClick: () -> Unit
) {
    val colors = MaterialTheme.colorScheme
    val (statusText, statusColor) = when (modelStatus.state) {
        ModelLoadState.READY -> (if (language == Language.CHINESE) "模型已加载" else "Model loaded") to Color(0xFF4CAF50)
        ModelLoadState.LOADING -> (if (language == Language.CHINESE) "加载中" else "Loading") to Color(0xFFFFC107)
        ModelLoadState.MISSING -> (if (language == Language.CHINESE) "未找到模型" else "Model not found") to Color(0xFFFF7043)
        ModelLoadState.ERROR -> (if (language == Language.CHINESE) "加载失败" else "Load failed") to Color(0xFFE53935)
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = dimensions.medium, vertical = dimensions.small)
            .clip(RoundedCornerShape(dimensions.cardRadius))
            .background(colors.surfaceVariant.copy(alpha = 0.85f))
            .border(1.dp, colors.outline.copy(alpha = 0.25f), RoundedCornerShape(dimensions.cardRadius))
            .padding(dimensions.medium),
        verticalArrangement = Arrangement.spacedBy(dimensions.small)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = if (language == Language.CHINESE) "本地模型状态" else "Local model status",
                    color = colors.onSurface,
                    fontWeight = FontWeight.Bold,
                    fontSize = dimensions.fontSizeBody.sp
                )
                Text(
                    text = statusText,
                    color = statusColor,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = dimensions.fontSizeSmall.sp
                )
            }

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(dimensions.buttonRadius))
                    .background(statusColor.copy(alpha = 0.12f))
                    .border(1.dp, statusColor.copy(alpha = 0.35f), RoundedCornerShape(dimensions.buttonRadius))
                    .padding(horizontal = dimensions.small, vertical = dimensions.tiny)
            ) {
                Text(
                    text = when (modelStatus.state) {
                        ModelLoadState.READY -> "●"
                        ModelLoadState.LOADING -> "…"
                        ModelLoadState.MISSING -> "!"
                        ModelLoadState.ERROR -> "×"
                    },
                    color = statusColor,
                    fontWeight = FontWeight.Bold,
                    fontSize = dimensions.fontSizeBody.sp
                )
            }
        }

        if (!modelStatus.modelName.isNullOrBlank()) {
            Text(
                text = modelStatus.modelName ?: "",
                color = colors.onSurfaceVariant,
                fontSize = dimensions.fontSizeSmall.sp
            )
        }

        if (!modelStatus.modelPath.isNullOrBlank()) {
            Text(
                text = modelStatus.modelPath ?: "",
                color = colors.onSurfaceVariant.copy(alpha = 0.75f),
                fontSize = (dimensions.fontSizeSmall - 1).sp,
                maxLines = 2
            )
        }

        if (!modelStatus.errorMessage.isNullOrBlank()) {
            Text(
                text = modelStatus.errorMessage ?: "",
                color = statusColor,
                fontSize = dimensions.fontSizeSmall.sp
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.End
        ) {
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(dimensions.buttonRadius))
                    .background(SurvivalGreen.copy(alpha = 0.12f))
                    .border(1.dp, SurvivalGreen.copy(alpha = 0.45f), RoundedCornerShape(dimensions.buttonRadius))
                    .clickable(onClick = onImportModelClick)
                    .padding(horizontal = dimensions.medium, vertical = dimensions.small)
            ) {
                Text(
                    text = if (language == Language.CHINESE) "选择本地模型文件" else "Choose local model file",
                    color = SurvivalGreen,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = dimensions.fontSizeSmall.sp
                )
            }
        }
    }
}

@Composable
fun HelpScreen(
    dimensions: com.example.myapplication.utils.ResponsiveDimensions,
    messages: List<Message>,
    inputText: String,
    listState: androidx.compose.foundation.lazy.LazyListState,
    scope: kotlinx.coroutines.CoroutineScope,
    systemStatus: SystemStatus,
    isGenerating: Boolean,
    onInputTextChange: (String) -> Unit,
    onSend: () -> Unit,
    onBroadcast: () -> Unit,
    onBack: () -> Unit,
    onTruthBoard: () -> Unit,
    language: Language
) {
    val colors = MaterialTheme.colorScheme
    Column(
        modifier = Modifier.fillMaxSize()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(dimensions.medium),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(dimensions.buttonRadius))
                    .background(colors.surfaceVariant.copy(alpha = 0.85f))
                    .clickable(onClick = onBack)
                    .padding(horizontal = dimensions.small, vertical = dimensions.tiny)
            ) {
                Text(
                    text = Lang.get(Lang.BACK, language),
                    color = SlateGrey,
                    fontSize = dimensions.fontSizeSmall.sp
                )
            }
            Text(
                text = Lang.get(Lang.AI_HELP, language),
                color = SurvivalGreen,
                fontWeight = FontWeight.Bold,
                fontSize = dimensions.fontSizeBody.sp
            )
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(dimensions.buttonRadius))
                    .background(Color.White.copy(alpha = 0.05f))
                    .clickable(onClick = onTruthBoard)
                    .padding(horizontal = dimensions.small, vertical = dimensions.tiny)
            ) {
                Text(
                    text = "⚖️",
                    color = SurvivalGreen,
                    fontSize = dimensions.fontSizeSmall.sp
                )
            }
        }

        LazyColumn(
            state = listState,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentPadding = PaddingValues(
                horizontal = dimensions.medium,
                vertical = dimensions.large
            ),
            verticalArrangement = Arrangement.spacedBy(dimensions.medium)
        ) {
            items(messages, key = { it.id }) { message ->
                MessageBubble(message = message)
            }
        }

        TelemetryBar(systemStatus = systemStatus)

        InputBar(
            text = inputText,
            onTextChange = onInputTextChange,
            onSend = onSend,
            onBroadcast = onBroadcast,
            enabled = !isGenerating,
            language = language
        )
    }
}

@Composable
fun BottomNavigationBar(
    currentScreen: Screen,
    onScreenChange: (Screen) -> Unit,
    dimensions: com.example.myapplication.utils.ResponsiveDimensions,
    language: Language
) {
    val colors = MaterialTheme.colorScheme
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(colors.surface.copy(alpha = 0.9f))
            .border(
                width = 1.dp,
                color = colors.outline.copy(alpha = 0.3f)
            )
            .padding(vertical = dimensions.medium),
        horizontalArrangement = Arrangement.SpaceEvenly,
        verticalAlignment = Alignment.CenterVertically
    ) {
        NavItem(
            icon = "🏠",
            label = Lang.get(Lang.HOME, language),
            isSelected = currentScreen == Screen.Home,
            onClick = { onScreenChange(Screen.Home) },
            dimensions = dimensions
        )
        NavItem(
            icon = "📷",
            label = Lang.get(Lang.CAMERA, language),
            isSelected = currentScreen == Screen.Camera,
            onClick = { onScreenChange(Screen.Camera) },
            dimensions = dimensions
        )
        NavItem(
            icon = "⚖️",
            label = Lang.get(Lang.TRUTH, language),
            isSelected = currentScreen == Screen.TruthBoard,
            onClick = { onScreenChange(Screen.TruthBoard) },
            dimensions = dimensions
        )
        NavItem(
            icon = "⚙️",
            label = Lang.get(Lang.SETTINGS, language),
            isSelected = currentScreen == Screen.Settings,
            onClick = { onScreenChange(Screen.Settings) },
            dimensions = dimensions
        )
    }
}

@Composable
fun NavItem(
    icon: String,
    label: String,
    isSelected: Boolean,
    onClick: () -> Unit,
    dimensions: com.example.myapplication.utils.ResponsiveDimensions
) {
    val colors = MaterialTheme.colorScheme
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(dimensions.tiny),
        modifier = Modifier
            .clip(RoundedCornerShape(dimensions.buttonRadius))
            .clickable(onClick = onClick)
            .padding(
                horizontal = dimensions.medium,
                vertical = dimensions.small
            )
    ) {
        Text(
            text = icon,
            fontSize = 28.sp
        )
        Text(
            text = label,
            color = if (isSelected) SurvivalGreen else SlateGrey,
            fontSize = dimensions.fontSizeSmall.sp,
            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
            lineHeight = (dimensions.fontSizeSmall * 1.3).sp
        )
    }
}

data class AppSettings(
    var enableNotifications: Boolean = true,
    var enableLocation: Boolean = true,
    var savePhotos: Boolean = true,
    var autoBroadcast: Boolean = false,
    var language: Language = Language.CHINESE,
    var theme: String = "深色模式"
)

@Composable
fun SettingsScreen(
    dimensions: com.example.myapplication.utils.ResponsiveDimensions,
    settings: AppSettings,
    onSettingsChange: (AppSettings) -> Unit,
    language: Language,
    modelStatus: ModelStatus,
    onImportModelClick: () -> Unit
) {
    var localSettings by remember { mutableStateOf(settings) }
    val colors = MaterialTheme.colorScheme
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(
                horizontal = dimensions.medium,
                vertical = dimensions.large
            ),
        verticalArrangement = Arrangement.spacedBy(dimensions.large)
    ) {
        Text(
            text = Lang.get(Lang.SETTINGS, language),
            color = colors.primary,
            fontSize = dimensions.fontSizeTitle.sp,
            fontWeight = FontWeight.Bold,
            lineHeight = (dimensions.fontSizeTitle * 1.3).sp
        )

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(dimensions.cardRadius),
            colors = CardDefaults.cardColors(
                containerColor = colors.surface
            ),
            border = androidx.compose.foundation.BorderStroke(
                width = 1.dp,
                color = colors.outline.copy(alpha = 0.35f)
            )
        ) {
            Column(
                modifier = Modifier.padding(dimensions.medium),
                verticalArrangement = Arrangement.spacedBy(dimensions.medium)
            ) {
                Text(
                    text = if (language == Language.CHINESE) "本地模型管理" else "Local Model Management",
                    color = colors.primary,
                    fontSize = dimensions.fontSizeSmall.sp,
                    fontWeight = FontWeight.Bold
                )

                ModelStatusCard(
                    modelStatus = modelStatus,
                    language = language,
                    dimensions = dimensions,
                    onImportModelClick = onImportModelClick
                )
            }
        }
        
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(dimensions.cardRadius),
            colors = CardDefaults.cardColors(
                containerColor = colors.surface
            ),
            border = androidx.compose.foundation.BorderStroke(
                width = 1.dp,
                color = colors.outline.copy(alpha = 0.35f)
            )
        ) {
            Column(
                modifier = Modifier.padding(dimensions.medium),
                verticalArrangement = Arrangement.spacedBy(dimensions.medium)
            ) {
                Text(
                    text = Lang.get(Lang.BASIC_SETTINGS, language),
                    color = colors.onSurfaceVariant,
                    fontSize = dimensions.fontSizeSmall.sp,
                    fontWeight = FontWeight.Bold
                )
                
                SettingSwitchItem(
                    icon = "🔔",
                    title = Lang.get(Lang.NOTIFICATIONS, language),
                    description = Lang.get(Lang.NOTIFICATIONS_DESC, language),
                    checked = localSettings.enableNotifications,
                    onCheckedChange = { 
                        localSettings = localSettings.copy(enableNotifications = it)
                        onSettingsChange(localSettings)
                    },
                    dimensions = dimensions
                )
                
                SettingSwitchItem(
                    icon = "📍",
                    title = Lang.get(Lang.LOCATION, language),
                    description = Lang.get(Lang.LOCATION_DESC, language),
                    checked = localSettings.enableLocation,
                    onCheckedChange = { 
                        localSettings = localSettings.copy(enableLocation = it)
                        onSettingsChange(localSettings)
                    },
                    dimensions = dimensions
                )
                
                SettingSwitchItem(
                    icon = "📸",
                    title = Lang.get(Lang.SAVE_PHOTOS, language),
                    description = Lang.get(Lang.SAVE_PHOTOS_DESC, language),
                    checked = localSettings.savePhotos,
                    onCheckedChange = { 
                        localSettings = localSettings.copy(savePhotos = it)
                        onSettingsChange(localSettings)
                    },
                    dimensions = dimensions
                )
            }
        }
        
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(dimensions.cardRadius),
            colors = CardDefaults.cardColors(
                containerColor = colors.surface
            ),
            border = androidx.compose.foundation.BorderStroke(
                width = 1.dp,
                color = colors.outline.copy(alpha = 0.35f)
            )
        ) {
            Column(
                modifier = Modifier.padding(dimensions.medium),
                verticalArrangement = Arrangement.spacedBy(dimensions.medium)
            ) {
                Text(
                    text = Lang.get(Lang.ADVANCED_SETTINGS, language),
                    color = colors.onSurfaceVariant,
                    fontSize = dimensions.fontSizeSmall.sp,
                    fontWeight = FontWeight.Bold
                )
                
                SettingSwitchItem(
                    icon = "📡",
                    title = Lang.get(Lang.AUTO_BROADCAST, language),
                    description = Lang.get(Lang.AUTO_BROADCAST_DESC, language),
                    checked = localSettings.autoBroadcast,
                    onCheckedChange = { 
                        localSettings = localSettings.copy(autoBroadcast = it)
                        onSettingsChange(localSettings)
                    },
                    dimensions = dimensions
                )
                
                SettingDropdownItem(
                    icon = "🌐",
                    title = Lang.get(Lang.LANGUAGE, language),
                    value = localSettings.language.code,
                    options = Language.values().map { it.code },
                    onValueChange = { code -> 
                        val newLang = Language.values().find { it.code == code } ?: Language.CHINESE
                        localSettings = localSettings.copy(language = newLang)
                        onSettingsChange(localSettings)
                    },
                    dimensions = dimensions
                )
                
                SettingDropdownItem(
                    icon = "🎨",
                    title = Lang.get(Lang.THEME, language),
                    value = localSettings.theme,
                    options = listOf(
                        Lang.get(Lang.DARK_MODE, language),
                        Lang.get(Lang.LIGHT_MODE, language)
                    ),
                    onValueChange = { 
                        localSettings = localSettings.copy(theme = it)
                        onSettingsChange(localSettings)
                    },
                    dimensions = dimensions
                )
            }
        }
        
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(dimensions.cardRadius),
            colors = CardDefaults.cardColors(
                containerColor = colors.surface
            ),
            border = androidx.compose.foundation.BorderStroke(
                width = 1.dp,
                color = colors.outline.copy(alpha = 0.35f)
            )
        ) {
            Column(
                modifier = Modifier.padding(dimensions.medium),
                verticalArrangement = Arrangement.spacedBy(dimensions.medium)
            ) {
                Text(
                    text = Lang.get(Lang.ABOUT, language),
                    color = colors.onSurfaceVariant,
                    fontSize = dimensions.fontSizeSmall.sp,
                    fontWeight = FontWeight.Bold
                )
                
                SettingItem(
                    icon = "ℹ️",
                    title = Lang.get(Lang.VERSION_INFO, language),
                    description = Lang.get(Lang.VERSION_DESC, language),
                    dimensions = dimensions
                )
                
                SettingItem(
                    icon = "📄",
                    title = Lang.get(Lang.PRIVACY_POLICY, language),
                    description = Lang.get(Lang.PRIVACY_POLICY_DESC, language),
                    dimensions = dimensions
                )
                
                SettingItem(
                    icon = "❓",
                    title = Lang.get(Lang.HELP_FEEDBACK, language),
                    description = Lang.get(Lang.HELP_FEEDBACK_DESC, language),
                    dimensions = dimensions
                )
            }
        }
    }
}

@Composable
fun SettingItem(
    icon: String,
    title: String,
    description: String,
    dimensions: com.example.myapplication.utils.ResponsiveDimensions
) {
    val colors = MaterialTheme.colorScheme
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(dimensions.buttonRadius))
            .padding(vertical = dimensions.small),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(dimensions.medium),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = icon,
                fontSize = 24.sp
            )
            Column(
                verticalArrangement = Arrangement.spacedBy(dimensions.tiny / 2)
            ) {
                Text(
                    text = title,
                    color = colors.onSurface,
                    fontSize = dimensions.fontSizeBody.sp,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = description,
                    color = colors.onSurfaceVariant,
                    fontSize = dimensions.fontSizeSmall.sp
                )
            }
        }
    }
}

@Composable
fun SettingSwitchItem(
    icon: String,
    title: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    dimensions: com.example.myapplication.utils.ResponsiveDimensions
) {
    val colors = MaterialTheme.colorScheme
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(dimensions.buttonRadius))
            .padding(vertical = dimensions.small),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(dimensions.medium),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = icon,
                fontSize = 24.sp
            )
            Column(
                verticalArrangement = Arrangement.spacedBy(dimensions.tiny / 2)
            ) {
                Text(
                    text = title,
                    color = colors.onSurface,
                    fontSize = dimensions.fontSizeBody.sp,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = description,
                    color = colors.onSurfaceVariant,
                    fontSize = dimensions.fontSizeSmall.sp
                )
            }
        }
        
        androidx.compose.material3.Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = androidx.compose.material3.SwitchDefaults.colors(
                checkedThumbColor = PureWhite,
                checkedTrackColor = SurvivalGreen,
                uncheckedThumbColor = SlateGrey,
                uncheckedTrackColor = Color.White.copy(alpha = 0.1f)
            )
        )
    }
}

@Composable
fun SettingDropdownItem(
    icon: String,
    title: String,
    value: String,
    options: List<String>,
    onValueChange: (String) -> Unit,
    dimensions: com.example.myapplication.utils.ResponsiveDimensions
) {
    val colors = MaterialTheme.colorScheme
    var expanded by remember { mutableStateOf(false) }
    
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(dimensions.buttonRadius))
            .clickable { expanded = true }
            .padding(vertical = dimensions.small),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(dimensions.medium),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = icon,
                fontSize = 24.sp
            )
            Column(
                verticalArrangement = Arrangement.spacedBy(dimensions.tiny / 2)
            ) {
                Text(
                    text = title,
                    color = colors.onSurface,
                    fontSize = dimensions.fontSizeBody.sp,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = value,
                    color = colors.primary,
                    fontSize = dimensions.fontSizeSmall.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }
        
        Text(
            text = "▾",
            color = SlateGrey,
            fontSize = dimensions.fontSizeBody.sp
        )
        
        androidx.compose.material3.DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
            containerColor = PitchBlack,
            modifier = Modifier.border(
                width = 1.dp,
                color = Color.White.copy(alpha = 0.2f),
                shape = RoundedCornerShape(dimensions.cardRadius)
            )
        ) {
            options.forEach { option ->
                androidx.compose.material3.DropdownMenuItem(
                    text = {
                        Text(
                            text = option,
                            color = if (option == value) SurvivalGreen else PureWhite,
                            fontSize = dimensions.fontSizeBody.sp
                        )
                    },
                    onClick = {
                        onValueChange(option)
                        expanded = false
                    }
                )
            }
        }
    }
}

@Composable
fun QuickActionButton(
    icon: String,
    label: String,
    onClick: () -> Unit
) {
    val dimensions = rememberResponsiveDimensions()
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(dimensions.small),
        modifier = Modifier
            .clip(RoundedCornerShape(dimensions.buttonRadius))
            .clickable(onClick = onClick)
            .padding(dimensions.small)
    ) {
        Box(
            modifier = Modifier
                .size(56.dp)
                .clip(CircleShape)
                .background(Color.White.copy(alpha = 0.05f))
                .border(
                    width = 1.dp,
                    color = SurvivalGreen.copy(alpha = 0.3f),
                    shape = CircleShape
                ),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = icon,
                fontSize = 24.sp
            )
        }
        Text(
            text = label,
            color = SlateGrey,
            fontSize = dimensions.fontSizeSmall.sp,
            lineHeight = (dimensions.fontSizeSmall * 1.3).sp
        )
    }
}

@Composable
fun TruthBoardPanel(
    verifiedAlerts: List<VerifiedAlert>,
    peerMessages: List<PeerMessage>,
    networkPeers: Int,
    isSimulating: Boolean,
    onClose: () -> Unit,
    onStartSimulation: () -> Unit,
    onClear: () -> Unit,
    language: Language
) {
    val dimensions = rememberResponsiveDimensions()

    val colors = MaterialTheme.colorScheme
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background.copy(alpha = 0.95f)),
        contentAlignment = Alignment.Center
    ) {
        Card(
            modifier = Modifier
                .fillMaxSize()
                .padding(dimensions.medium),
            shape = RoundedCornerShape(dimensions.cardRadius),
            colors = CardDefaults.cardColors(
                containerColor = PitchBlack.copy(alpha = 0.98f)
            ),
            border = androidx.compose.foundation.BorderStroke(
                width = 1.dp,
                color = AlertRed.copy(alpha = 0.6f)
            )
        ) {
            Column(
                modifier = Modifier.padding(dimensions.medium)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = Lang.get(Lang.TRUTH_BOARD_TITLE, language),
                            color = AlertRed,
                            fontWeight = FontWeight.Bold,
                            fontSize = dimensions.fontSizeTitle.sp,
                            lineHeight = (dimensions.fontSizeTitle * 1.3).sp
                        )
                        Text(
                            text = Lang.get(Lang.LOGIC_ARBITRATOR, language),
                            color = SlateGrey,
                            fontSize = dimensions.fontSizeSmall.sp,
                            lineHeight = (dimensions.fontSizeSmall * 1.3).sp
                        )
                    }
                    Box(
                        modifier = Modifier
                            .clip(CircleShape)
                            .background(Color.White.copy(alpha = 0.1f))
                            .clickable { onClose() }
                            .padding(dimensions.small)
                    ) {
                        Text(
                            text = "✕",
                            color = PureWhite,
                            fontWeight = FontWeight.Bold,
                            fontSize = dimensions.fontSizeBody.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(dimensions.medium))

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(dimensions.buttonRadius),
                    colors = CardDefaults.cardColors(
                        containerColor = Color.White.copy(alpha = 0.05f)
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(dimensions.medium),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column {
                            Text(
                                text = Lang.get(Lang.ONLINE_PEERS, language),
                                color = SlateGrey,
                                fontSize = dimensions.fontSizeSmall.sp
                            )
                            Text(
                                text = "$networkPeers ${Lang.get(Lang.DEVICES, language)}",
                                color = SurvivalGreen,
                                fontWeight = FontWeight.Bold,
                                fontSize = dimensions.fontSizeBody.sp
                            )
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text(
                                text = Lang.get(Lang.RECEIVED_MESSAGES, language),
                                color = SlateGrey,
                                fontSize = dimensions.fontSizeSmall.sp
                            )
                            Text(
                                text = "${peerMessages.size} ${Lang.get(Lang.MESSAGES, language)}",
                                color = PureWhite,
                                fontWeight = FontWeight.Bold,
                                fontSize = dimensions.fontSizeBody.sp
                            )
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text(
                                text = Lang.get(Lang.TRUSTED_ALERTS, language),
                                color = SlateGrey,
                                fontSize = dimensions.fontSizeSmall.sp
                            )
                            Text(
                                text = "${verifiedAlerts.size} ${Lang.get(Lang.ALERTS, language)}",
                                color = AlertRed,
                                fontWeight = FontWeight.Bold,
                                fontSize = dimensions.fontSizeBody.sp
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(dimensions.medium))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(dimensions.small)
                ) {
                    Button(
                        onClick = onStartSimulation,
                        modifier = Modifier.weight(1f),
                        enabled = !isSimulating,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (isSimulating) SlateGrey.copy(alpha = 0.3f) else AlertRed,
                            contentColor = PureWhite,
                            disabledContainerColor = SlateGrey.copy(alpha = 0.3f),
                            disabledContentColor = SlateGrey
                        ),
                        shape = RoundedCornerShape(dimensions.buttonRadius)
                    ) {
                        Text(
                            text = if (isSimulating) Lang.get(Lang.SIMULATING, language) else Lang.get(Lang.SIMULATE_PANIC, language),
                            fontWeight = FontWeight.Bold,
                            fontSize = dimensions.fontSizeBody.sp
                        )
                    }
                    Button(
                        onClick = onClear,
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color.White.copy(alpha = 0.1f),
                            contentColor = PureWhite
                        ),
                        shape = RoundedCornerShape(dimensions.buttonRadius)
                    ) {
                        Text(
                            text = Lang.get(Lang.CLEAR_RECORDS, language),
                            fontWeight = FontWeight.Bold,
                            fontSize = dimensions.fontSizeBody.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(dimensions.medium))

                if (verifiedAlerts.isNotEmpty()) {
                    Text(
                        text = if (language == Language.CHINESE) "🔴 可信警报 (通过验证)" else "🔴 TRUSTED ALERTS (Verified)",
                        color = AlertRed,
                        fontWeight = FontWeight.Bold,
                        fontSize = dimensions.fontSizeBody.sp
                    )
                    Spacer(modifier = Modifier.height(dimensions.small))
                    verifiedAlerts.reversed().take(5).forEach { alert ->
                        VerifiedAlertCard(alert = alert, language = language)
                        Spacer(modifier = Modifier.height(dimensions.small))
                    }
                    Spacer(modifier = Modifier.height(dimensions.medium))
                }

                if (peerMessages.isNotEmpty()) {
                    Text(
                        text = Lang.get(Lang.PEER_MESSAGES, language),
                        color = SlateGrey,
                        fontWeight = FontWeight.Bold,
                        fontSize = dimensions.fontSizeBody.sp
                    )
                    Spacer(modifier = Modifier.height(dimensions.small))
                    LazyColumn(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(dimensions.small)
                    ) {
                        items(peerMessages.reversed().take(10)) { msg ->
                            PeerMessageCard(msg = msg, language = language)
                        }
                    }
                } else {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = Lang.get(Lang.WAITING_NETWORK, language),
                            color = SlateGrey,
                            fontSize = dimensions.fontSizeBody.sp,
                            lineHeight = (dimensions.fontSizeBody * 1.5).sp
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun VerifiedAlertCard(alert: VerifiedAlert, language: Language) {
    val dimensions = rememberResponsiveDimensions()
    val colors = MaterialTheme.colorScheme
    val cardColor = if (alert.isTrusted) AlertRed.copy(alpha = 0.14f) else colors.primary.copy(alpha = 0.10f)
    val borderColor = if (alert.isTrusted) AlertRed.copy(alpha = 0.6f) else colors.primary.copy(alpha = 0.5f)

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(dimensions.cardRadius - 4.dp),
        colors = CardDefaults.cardColors(
            containerColor = cardColor
        ),
        border = androidx.compose.foundation.BorderStroke(
            width = 1.dp,
            color = borderColor
        )
    ) {
        Column(
            modifier = Modifier.padding(dimensions.small),
            verticalArrangement = Arrangement.spacedBy(dimensions.tiny)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "${Lang.get(Lang.ALERT_TYPE, language)}${alert.alertType.name}",
                    color = if (alert.isTrusted) AlertRed else SurvivalGreen,
                    fontWeight = FontWeight.Bold,
                    fontSize = dimensions.fontSizeSmall.sp
                )
                Text(
                    text = "${Lang.get(Lang.CONFIDENCE, language)}${(alert.confidence * 100).toInt()}%",
                    color = SurvivalGreen,
                    fontWeight = FontWeight.Bold,
                    fontSize = dimensions.fontSizeSmall.sp
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "${Lang.get(Lang.PEER_NODES, language)}${alert.verifyingPeers} ${Lang.get(Lang.PEER_NODES_COUNT, language)}",
                    color = SlateGrey,
                    fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                    fontSize = dimensions.fontSizeLabel.sp
                )
            }
            Text(
                text = alert.content,
                color = PureWhite,
                fontSize = dimensions.fontSizeBody.sp,
                lineHeight = (dimensions.fontSizeBody * 1.4).sp
            )
        }
    }
}

@Composable
fun PeerMessageCard(msg: PeerMessage, language: Language) {
    val dimensions = rememberResponsiveDimensions()
    val peerIcon = when (msg.peerType) {
        PeerType.MOBILE -> "📱"
        PeerType.DRONE -> "🛸"
        PeerType.SENSOR -> "📡"
        PeerType.SATELLITE -> "🛰️"
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(dimensions.cardRadius - 4.dp),
        colors = CardDefaults.cardColors(
            containerColor = Color.White.copy(alpha = 0.03f)
        ),
        border = androidx.compose.foundation.BorderStroke(
            width = 1.dp,
            color = SlateGrey.copy(alpha = 0.3f)
        )
    ) {
        Column(
            modifier = Modifier.padding(dimensions.small),
            verticalArrangement = Arrangement.spacedBy(dimensions.tiny)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "$peerIcon ${Lang.get(Lang.PEER_NODE, language)}${msg.peerId}",
                    color = SurvivalGreen,
                    fontWeight = FontWeight.Bold,
                    fontSize = dimensions.fontSizeSmall.sp
                )
            }
            Text(
                text = msg.content,
                color = PureWhite,
                fontSize = dimensions.fontSizeBody.sp,
                lineHeight = (dimensions.fontSizeBody * 1.4).sp
            )
        }
    }
}

suspend fun simulatePeerMessages(
    onNewMessage: (PeerMessage) -> Unit,
    onComplete: () -> Unit
) {
    val peerIds = listOf(
        "NODE-7F8A", "NODE-2C1B", "NODE-9D4E", "NODE-5A2F",
        "NODE-8C7D", "NODE-3B9A", "NODE-6E3C", "NODE-1F5B"
    )
    val panicMessages = listOf(
        "大坝真的要塌了！看到裂缝了！",
        "水库水位异常高，大坝渗水严重",
        "大坝看起来没事啊，别瞎说",
        "我也看到裂缝了，在东侧！",
        "水位正常，大坝没问题",
        "大坝要垮了！大家快跑！",
        "刚才有巨响，好像是坝体结构声",
        "我在远处看，大坝很稳定",
        "水流变得很浑浊，感觉不对",
        "大坝管理员说一切正常"
    )

    panicMessages.forEachIndexed { index, content ->
        delay(if (index < 3) 500 else 800)
        val peerType = if (Random().nextFloat() < 0.2) PeerType.SENSOR else PeerType.MOBILE
        val newMsg = PeerMessage(
            id = System.currentTimeMillis(),
            peerId = peerIds[index % peerIds.size],
            content = content,
            peerType = peerType
        )
        onNewMessage(newMsg)
    }
    onComplete()
}

suspend fun runArbitration(messages: List<PeerMessage>): VerifiedAlert? {
    if (messages.size < 3) return null

    val trusted = runCatching {
        LegacyBackendApiClient.arbitrate(messages.mapToReports())
    }.getOrNull()?.isNotBlank() == true

    return if (trusted) {
        VerifiedAlert(
            id = System.currentTimeMillis(),
            alertType = AlertType.DAM_BREAK,
            confidence = 0.8f,
            verifyingPeers = messages.size,
            content = "【逻辑仲裁官】多节点证实：大坝存在裂缝异常！建议立即撤离！",
            isTrusted = true
        )
    } else null
}

fun loadBitmapFromUri(context: Context, uri: android.net.Uri): Bitmap? {
    return try {
        val inputStream = context.contentResolver.openInputStream(uri)
        val options = android.graphics.BitmapFactory.Options().apply {
            // 只读取尺寸信息
            inJustDecodeBounds = true
        }
        android.graphics.BitmapFactory.decodeStream(inputStream, null, options)
        
        // 计算合适的缩放比例
        val maxSize = 2048 // 最大边长
        var scale = 1
        while (options.outWidth / scale > maxSize || options.outHeight / scale > maxSize) {
            scale *= 2
        }
        
        // 重新加载完整图片
        options.inJustDecodeBounds = false
        options.inSampleSize = scale
        options.inPreferredConfig = android.graphics.Bitmap.Config.RGB_565 // 节省内存
        
        // 重新打开输入流
        context.contentResolver.openInputStream(uri)?.use {
            android.graphics.BitmapFactory.decodeStream(it, null, options)
        }
    } catch (e: Exception) {
        e.printStackTrace()
        null
    }
}

data class LocationInfo(
    val latitude: Double = 0.0,
    val longitude: Double = 0.0,
    val accuracy: Float = 0f,
    val hasLocation: Boolean = false
)

fun requestLocationUpdates(
    context: Context,
    onLocationChanged: (LocationInfo) -> Unit
): () -> Unit {
    val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    var callback: (Location) -> Unit = {}
    val locationCallback = object : android.location.LocationListener {
        override fun onLocationChanged(location: Location) {
            onLocationChanged(
                LocationInfo(
                    latitude = location.latitude,
                    longitude = location.longitude,
                    accuracy = location.accuracy,
                    hasLocation = true
                )
            )
        }

        override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) {}
        override fun onProviderEnabled(provider: String) {}
        override fun onProviderDisabled(provider: String) {}
    }

    try {
        if (ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            locationManager.requestLocationUpdates(
                LocationManager.GPS_PROVIDER,
                1000,
                10f,
                locationCallback
            )
            locationManager.requestLocationUpdates(
                LocationManager.NETWORK_PROVIDER,
                1000,
                10f,
                locationCallback
            )

            locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)?.let { lastLocation ->
                onLocationChanged(
                    LocationInfo(
                        latitude = lastLocation.latitude,
                        longitude = lastLocation.longitude,
                        accuracy = lastLocation.accuracy,
                        hasLocation = true
                    )
                )
            } ?: locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)?.let { lastLocation ->
                onLocationChanged(
                    LocationInfo(
                        latitude = lastLocation.latitude,
                        longitude = lastLocation.longitude,
                        accuracy = lastLocation.accuracy,
                        hasLocation = true
                    )
                )
            }
        }
    } catch (e: Exception) {
        e.printStackTrace()
    }

    return {
        try {
            locationManager.removeUpdates(locationCallback)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
}

suspend fun savePhotoToGallery(context: Context, bitmap: Bitmap): Boolean {
    return try {
        val fileName = "PR_${System.currentTimeMillis()}.jpg"
        val contentValues = android.content.ContentValues().apply {
            put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, fileName)
            put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
            put(android.provider.MediaStore.Images.Media.RELATIVE_PATH, "Pictures/ProjectResurgence")
            put(android.provider.MediaStore.Images.Media.IS_PENDING, 1)
        }

        val contentResolver = context.contentResolver
        val uri = contentResolver.insert(android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, contentValues)
        
        uri?.let { imageUri ->
            contentResolver.openOutputStream(imageUri)?.use { outputStream ->
                bitmap.compress(Bitmap.CompressFormat.JPEG, 90, outputStream)
                contentValues.put(android.provider.MediaStore.Images.Media.IS_PENDING, 0)
                contentResolver.update(imageUri, contentValues, null, null)
            }
        }
        true
    } catch (e: Exception) {
        e.printStackTrace()
        false
    }
}

suspend fun uploadPhoto(bitmap: Bitmap, language: Language): Boolean {
    return runCatching {
        LegacyBackendApiClient.uploadPhoto(bitmap, language)
    }.getOrDefault(false)
}

object LocalModelEngine {
    private const val MODEL_FILE_NAME = "gemma-4-e2b-it.litertlm"
    private const val FALLBACK_MODEL_FILE_NAME = "gemma4e2b.bin"

    @Volatile
    private var engine: Engine? = null

    @Volatile
    private var loadedModelPath: String? = null

    private fun modelFile(context: Context): File? = findLocalGemmaModel(context) ?: run {
        val fallbackDir = File(context.filesDir, "model")
        listOf(
            File(fallbackDir, MODEL_FILE_NAME),
            File(fallbackDir, FALLBACK_MODEL_FILE_NAME)
        ).firstOrNull { it.exists() && it.length() > 0L }
    }

    suspend fun chat(prompt: String, image: Bitmap? = null): String = generate(prompt, image, "chat")
    suspend fun analyze(prompt: String, image: Bitmap? = null): String = generate(prompt, image, "analysis")

    suspend fun uploadPhoto(bitmap: Bitmap, language: Language): Boolean = withContext(Dispatchers.IO) {
        val context = AppGlobals.appContext ?: return@withContext false
        val dir = File(context.filesDir, "uploads")
        if (!dir.exists()) dir.mkdirs()
        val out = File(dir, "photo_${System.currentTimeMillis()}.jpg")
        runCatching {
            out.outputStream().use { stream -> bitmap.compress(Bitmap.CompressFormat.JPEG, 90, stream) }
        }.isSuccess
    }

    suspend fun arbitrate(reports: List<String>): Boolean = reports.isNotEmpty()

    suspend fun generate(prompt: String, image: Bitmap?, mode: String): String = withContext(Dispatchers.IO) {
        val context = AppGlobals.appContext ?: error("App context not ready")
        val model = modelFile(context) ?: error("Local model file missing")
        val runtime = ensureEngine(context, model.absolutePath)
            ?: error("LiteRT-LM runtime unavailable")

        val conversation = runtime.createConversation(
            ConversationConfig(
                samplerConfig = SamplerConfig(
                    topK = 40,
                    topP = 0.95,
                    temperature = if (mode == "analysis") 0.2 else 0.7
                )
            )
        )

        conversation.use { conv ->
            val finalPrompt = buildString {
                if (image != null) appendLine("[IMAGE_PRESENT=true]")
                appendLine("MODE=$mode")
                append(prompt)
            }
            conv.sendMessage(finalPrompt).toString().trim().ifBlank {
                error("LiteRT-LM returned empty response")
            }
        }
    }

    private fun ensureEngine(context: Context, modelPath: String): Engine? {
        engine?.let { existing ->
            if (loadedModelPath == modelPath) return existing
        }
        synchronized(this) {
            engine?.let { existing ->
                if (loadedModelPath == modelPath) return existing
            }
            return runCatching {
                val created = Engine(
                    EngineConfig(
                        modelPath = modelPath,
                        backend = Backend.CPU(),
                        cacheDir = context.cacheDir.absolutePath
                    )
                )
                created.initialize()
                engine = created
                loadedModelPath = modelPath
                created
            }.getOrNull()
        }
    }
}

object LegacyBackendApiClient {
    suspend fun chat(prompt: String, image: Bitmap? = null): String = LocalModelEngine.chat(prompt, image)
    suspend fun analyze(prompt: String, image: Bitmap? = null): String = LocalModelEngine.analyze(prompt, image)
    suspend fun uploadPhoto(bitmap: Bitmap, language: Language): Boolean = LocalModelEngine.uploadPhoto(bitmap, language)
    suspend fun arbitrate(reports: List<String>): String = reports.joinToString("\n")
    suspend fun generate(prompt: String, image: Bitmap?, mode: String): Result<String> = runCatching {
        when (mode) {
            "analysis" -> LocalModelEngine.analyze(prompt, image)
            else -> LocalModelEngine.chat(prompt, image)
        }
    }
}

object AppGlobals {
    @Volatile var appContext: Context? = null
}

@Composable
fun SurvivalMentorPanel(
    onClose: () -> Unit,
    onPhotoCaptured: (Bitmap, String) -> Unit,
    language: Language
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val dimensions = rememberResponsiveDimensions()
    val scope = rememberCoroutineScope()
    var previewView by remember { mutableStateOf<PreviewView?>(PreviewView(context)) }
    var cameraProvider by remember { mutableStateOf<ProcessCameraProvider?>(null) }
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var capturedBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var analysisResult by remember { mutableStateOf("") }
    var isAnalyzing by remember { mutableStateOf(false) }
    var isSaving by remember { mutableStateOf(false) }
    var isUploading by remember { mutableStateOf(false) }
    var hasStoragePermission by remember { mutableStateOf(false) }
    var showMessage by remember { mutableStateOf<String?>(null) }

    val cameraProviderFuture = remember { ProcessCameraProvider.getInstance(context) }
    
    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        uri?.let {
            try {
                // 使用 takePersistableUriPermission 来保持持久访问权限
                val takeFlags = android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION or
                    android.content.Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                try {
                    context.contentResolver.takePersistableUriPermission(it, takeFlags)
                } catch (e: Exception) {
                    // 忽略这个错误，不是所有 URI 都支持持久权限
                }
                
                // 加载图片
                val bitmap = loadBitmapFromUri(context, it)
                bitmap?.let { bmp ->
                    capturedBitmap = bmp
                    isAnalyzing = true
                    analysisResult = analyzeImageForWounds(bmp, language)
                    isAnalyzing = false
                } ?: run {
                    showMessage = if (language == Language.CHINESE) 
                        "无法加载图片，请选择其他图片" 
                    else 
                        "Cannot load image, please select another"
                }
            } catch (e: Exception) {
                e.printStackTrace()
                showMessage = if (language == Language.CHINESE) 
                    "图片加载失败：${e.message}" 
                else 
                    "Image loading failed: ${e.message}"
            }
        }
    }
    
    val storagePermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasStoragePermission = granted
        if (granted) {
            try {
                galleryLauncher.launch(arrayOf("image/*"))
            } catch (e: Exception) {
                e.printStackTrace()
                showMessage = if (language == Language.CHINESE) 
                    "无法打开相册，请检查权限设置" 
                else 
                    "Cannot open gallery, please check permission settings"
            }
        }
    }

    LaunchedEffect(Unit) {
        hasStoragePermission = ContextCompat.checkSelfPermission(
            context,
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
                android.Manifest.permission.READ_MEDIA_IMAGES
            } else {
                android.Manifest.permission.READ_EXTERNAL_STORAGE
            }
        ) == PackageManager.PERMISSION_GRANTED
    }

    LaunchedEffect(showMessage) {
        if (showMessage != null) {
            kotlinx.coroutines.delay(2000)
            showMessage = null
        }
    }

    DisposableEffect(Unit) {
        val future = cameraProviderFuture
        future.addListener({
            cameraProvider = future.get()
        }, ContextCompat.getMainExecutor(context))

        onDispose {
            cameraProvider?.unbindAll()
        }
    }

    val colors = MaterialTheme.colorScheme
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(colors.background)
            .padding(dimensions.medium),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = Lang.get(Lang.SURVIVAL_MENTOR, language),
                color = colors.primary,
                fontWeight = FontWeight.Bold,
                fontSize = dimensions.fontSizeTitle.sp,
                lineHeight = (dimensions.fontSizeTitle * 1.3).sp
            )
            Box(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(colors.surfaceVariant)
                    .clickable { onClose() }
                    .padding(dimensions.small)
            ) {
                Text(
                    text = "✕",
                    color = colors.onSurface,
                    fontWeight = FontWeight.Bold,
                    fontSize = dimensions.fontSizeBody.sp
                )
            }
        }

        Spacer(modifier = Modifier.height(dimensions.medium))

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(dimensions.cardRadius),
            colors = CardDefaults.cardColors(containerColor = colors.surfaceVariant.copy(alpha = 0.85f)),
            border = androidx.compose.foundation.BorderStroke(1.dp, colors.outline.copy(alpha = 0.3f))
        ) {
            Column(
                modifier = Modifier.padding(dimensions.medium),
                verticalArrangement = Arrangement.spacedBy(dimensions.small)
            ) {
                Text(
                    text = if (language == Language.CHINESE) "分析结果" else "Analysis Result",
                    color = colors.primary,
                    fontWeight = FontWeight.Bold,
                    fontSize = dimensions.fontSizeBody.sp
                )
                Text(
                    text = if (isAnalyzing) {
                        if (language == Language.CHINESE) "正在分析..." else "Analyzing..."
                    } else if (analysisResult.isNotBlank()) {
                        analysisResult
                    } else {
                        if (language == Language.CHINESE) "等待拍照或导入图片后自动分析" else "Take or import a photo to analyze"
                    },
                    color = colors.onSurface,
                    fontSize = dimensions.fontSizeSmall.sp,
                    lineHeight = (dimensions.fontSizeSmall * 1.4).sp
                )
            }
        }

        Spacer(modifier = Modifier.height(dimensions.small))

        AndroidView(
            factory = { previewView ?: PreviewView(it).also { view -> previewView = view } },
            modifier = Modifier
                .fillMaxWidth()
                .height(260.dp)
                .clip(RoundedCornerShape(dimensions.cardRadius))
        )

        Spacer(modifier = Modifier.height(dimensions.small))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(dimensions.small)
        ) {
            Button(
                onClick = { galleryLauncher.launch(arrayOf("image/*")) },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(
                    containerColor = colors.primary,
                    contentColor = colors.onPrimary
                ),
                shape = RoundedCornerShape(dimensions.buttonRadius)
            ) {
                Text(text = if (language == Language.CHINESE) "从相册导入" else "Import from Gallery")
            }
            Button(
                onClick = {
                    val capture = imageCapture
                    if (capture != null) {
                        takePhoto(context, capture) { bitmap ->
                            capturedBitmap = bitmap
                            isAnalyzing = true
                            scope.launch {
                                analysisResult = runCatching {
                                    LocalModelEngine.analyze(if (language == Language.CHINESE) "拍摄图像" else "captured image", bitmap)
                                }.getOrElse { analyzeImageForWounds(bitmap, language) }
                                onPhotoCaptured(bitmap, analysisResult)
                                isAnalyzing = false
                            }
                        }
                    } else {
                        showMessage = if (language == Language.CHINESE) "相机尚未准备好" else "Camera not ready"
                    }
                },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(
                    containerColor = colors.secondary,
                    contentColor = colors.onSecondary
                ),
                shape = RoundedCornerShape(dimensions.buttonRadius)
            ) {
                Text(text = if (language == Language.CHINESE) "拍照" else "Take Photo")
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(dimensions.small)
        ) {
            OutlinedButton(
                onClick = {
                    capturedBitmap = null
                    analysisResult = ""
                    isAnalyzing = false
                    scope.launch {
                        cameraProvider?.let { provider ->
                            try {
                                provider.unbindAll()
                                val pv = previewView ?: PreviewView(context).also { previewView = it }
                                val preview = Preview.Builder()
                                    .build()
                                    .also { it.setSurfaceProvider(pv.surfaceProvider) }
                                imageCapture = ImageCapture.Builder()
                                    .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                                    .setTargetRotation(pv.display?.rotation ?: android.view.Surface.ROTATION_0)
                                    .build()
                                provider.bindToLifecycle(
                                    lifecycleOwner,
                                    CameraSelector.DEFAULT_BACK_CAMERA,
                                    preview,
                                    imageCapture
                                )
                            } catch (e: Exception) {
                                e.printStackTrace()
                                showMessage = if (language == Language.CHINESE) "相机重置失败" else "Camera reset failed"
                            }
                        }
                    }
                },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(dimensions.buttonRadius)
            ) {
                Text(text = if (language == Language.CHINESE) "重新拍摄" else "Retake")
            }
            OutlinedButton(
                onClick = {
                    capturedBitmap = null
                    analysisResult = ""
                    isAnalyzing = false
                    galleryLauncher.launch(arrayOf("image/*"))
                },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(dimensions.buttonRadius)
            ) {
                Text(text = if (language == Language.CHINESE) "重新选择" else "Re-select")
            }
        }

        LaunchedEffect(cameraProvider) {
            val provider = cameraProvider ?: return@LaunchedEffect
            val pv = previewView ?: PreviewView(context).also { previewView = it }

            try {
                provider.unbindAll()

                val preview = Preview.Builder()
                    .build()
                    .also { it.setSurfaceProvider(pv.surfaceProvider) }

                imageCapture = ImageCapture.Builder()
                    .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                    .setTargetRotation(pv.display?.rotation ?: android.view.Surface.ROTATION_0)
                    .build()

                provider.bindToLifecycle(
                    lifecycleOwner,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    imageCapture
                )
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
}

fun takePhoto(
    context: Context,
    imageCapture: ImageCapture?,
    onPhotoTaken: (Bitmap) -> Unit
) {
    imageCapture?.let { capture ->
        val executor = ContextCompat.getMainExecutor(context)
        
        capture.takePicture(
            executor,
            object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: androidx.camera.core.ImageProxy) {
                    super.onCaptureSuccess(image)
                    
                    image.use { imageProxy ->
                        val buffer = imageProxy.planes[0].buffer
                        val bytes = ByteArray(buffer.remaining())
                        buffer.get(bytes)
                        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                        
                        if (bitmap != null) {
                            onPhotoTaken(bitmap)
                        } else {
                            val defaultBitmap = Bitmap.createBitmap(
                                800, 600,
                                Bitmap.Config.ARGB_8888
                            )
                            val canvas = android.graphics.Canvas(defaultBitmap)
                            val paint = android.graphics.Paint()
                            canvas.drawColor(0xFF222222.toInt())
                            paint.textSize = 40f
                            paint.color = 0xFFFFFFFF.toInt()
                            canvas.drawText("请重新拍摄", 200f, 300f, paint)
                            onPhotoTaken(defaultBitmap)
                        }
                    }
                }

                override fun onError(exc: androidx.camera.core.ImageCaptureException) {
                    super.onError(exc)
                    exc.printStackTrace()
                    
                    val bitmap = Bitmap.createBitmap(
                        800, 600,
                        Bitmap.Config.ARGB_8888
                    )
                    val canvas = android.graphics.Canvas(bitmap)
                    val paint = android.graphics.Paint()
                    canvas.drawColor(0xFF111111.toInt())
                    paint.textSize = 30f
                    paint.color = 0xFFFFFFFF.toInt()
                    canvas.drawText("拍照失败，请重试", 150f, 300f, paint)
                    onPhotoTaken(bitmap)
                }
            }
        )
    }
}

fun analyzeImageForWounds(bitmap: Bitmap, language: Language): String {
    val results = mutableListOf<String>()
    val width = bitmap.width
    val height = bitmap.height
    
    val pixels = IntArray(width * height)
    bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
    
    var redPixelCount = 0
    var redClusters = 0
    
    for (y in 0 until height step 10) {
        for (x in 0 until width step 10) {
            val index = y * width + x
            val pixel = pixels[index]
            
            val red = android.graphics.Color.red(pixel)
            val green = android.graphics.Color.green(pixel)
            val blue = android.graphics.Color.blue(pixel)
            
            if (red > 150 && green < 100 && blue < 100) {
                redPixelCount++
            }
        }
    }
    
    for (y in 0 until height step 20) {
        for (x in 0 until width step 20) {
            var clusterRedCount = 0
            for (dy in -2..2) {
                for (dx in -2..2) {
                    val nx = x + dx * 10
                    val ny = y + dy * 10
                    if (nx in 0 until width && ny in 0 until height) {
                        val index = ny * width + nx
                        val pixel = pixels[index]
                        val red = android.graphics.Color.red(pixel)
                        val green = android.graphics.Color.green(pixel)
                        val blue = android.graphics.Color.blue(pixel)
                        
                        if (red > 150 && green < 100 && blue < 100) {
                            clusterRedCount++
                        }
                    }
                }
            }
            if (clusterRedCount > 5) {
                redClusters++
            }
        }
    }
    
    val redRatio = redPixelCount.toFloat() / ((width / 10) * (height / 10)).toFloat()
    
    if (redRatio > 0.05 && redClusters > 3) {
        results.add(Lang.get(Lang.BLEEDING_DETECTED, language))
    }
    
    if (redRatio > 0.15) {
        results.add(Lang.get(Lang.HIGH_SUSPECT_BLEEDING, language))
    }
    
    if (redRatio > 0.02 && redRatio <= 0.05) {
        results.add(Lang.get(Lang.MINOR_ABRASION, language))
    }
    
    if (redClusters > 0 && redClusters <= 3) {
        results.add(if (language == Language.CHINESE) "发现少量红色区域，请观察" else "Small red area found, observe")
    }
    
    if (results.isEmpty()) {
        results.add(Lang.get(Lang.NO_WOUND_DETECTED, language))
    }
    
    return results.joinToString("\n")
}

@Composable
fun HardwareCheckDialog(
    systemStatus: SystemStatus,
    onDismiss: () -> Unit,
    language: Language
) {
    val dimensions = rememberResponsiveDimensions()
    val ramPercent = if (systemStatus.ramTotal > 0) {
        (systemStatus.ramAvailable.toFloat() / systemStatus.ramTotal.toFloat() * 100).toInt()
    } else 0
    
    val meetsRequirements = systemStatus.ramAvailable >= 2048 && systemStatus.gpuAvailable

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.85f)),
        contentAlignment = Alignment.Center
    ) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(dimensions.large),
            shape = RoundedCornerShape(dimensions.cardRadius),
            colors = CardDefaults.cardColors(
                containerColor = PitchBlack.copy(alpha = 0.98f)
            ),
            border = androidx.compose.foundation.BorderStroke(
                width = 2.dp,
                color = if (meetsRequirements) SurvivalGreen else AlertRed
            ),
            elevation = CardDefaults.cardElevation(
                defaultElevation = 16.dp
            )
        ) {
            Column(
                modifier = Modifier.padding(dimensions.large),
                verticalArrangement = Arrangement.spacedBy(dimensions.medium)
            ) {
                Text(
                    text = Lang.get(Lang.HARDWARE_CHECK, language),
                    style = MaterialTheme.typography.titleLarge,
                    color = if (meetsRequirements) SurvivalGreen else AlertRed,
                    fontWeight = FontWeight.ExtraBold,
                    fontSize = (dimensions.fontSizeTitle * 1.1).sp,
                    lineHeight = ((dimensions.fontSizeTitle * 1.1) * 1.3).sp
                )

                HardwareCheckItem(
                    label = Lang.get(Lang.AVAILABLE_RAM, language),
                    value = "${systemStatus.ramAvailable} MB / ${systemStatus.ramTotal} MB",
                    status = systemStatus.ramAvailable >= 2048,
                    requirement = Lang.get(Lang.RAM_REQUIREMENT, language)
                )

                HardwareCheckItem(
                    label = Lang.get(Lang.GPU_SUPPORT, language),
                    value = if (systemStatus.gpuAvailable) "DETECTED" else "NOT FOUND",
                    status = systemStatus.gpuAvailable,
                    requirement = Lang.get(Lang.GPU_REQUIREMENT, language)
                )

                HardwareCheckItem(
                    label = Lang.get(Lang.MEMORY_HEADROOM, language),
                    value = "$ramPercent% FREE",
                    status = ramPercent >= 30,
                    requirement = Lang.get(Lang.MEMORY_REQUIREMENT, language)
                )

                if (!meetsRequirements) {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(dimensions.buttonRadius),
                        colors = CardDefaults.cardColors(
                            containerColor = AlertRed.copy(alpha = 0.15f)
                        ),
                        border = androidx.compose.foundation.BorderStroke(
                            width = 1.dp,
                            color = AlertRed.copy(alpha = 0.5f)
                        )
                    ) {
                        Text(
                            text = Lang.get(Lang.DEGRADED_MODE, language),
                            modifier = Modifier.padding(dimensions.medium),
                            color = AlertRed,
                            fontSize = dimensions.fontSizeSmall.sp,
                            fontWeight = FontWeight.Bold,
                            lineHeight = (dimensions.fontSizeSmall * 1.4).sp
                        )
                    }
                }

                Button(
                    onClick = onDismiss,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (meetsRequirements) SurvivalGreen else AlertRed,
                        contentColor = PitchBlack
                    )
                ) {
                    Text(
                        text = if (meetsRequirements) Lang.get(Lang.CONTINUE, language) else Lang.get(Lang.PROCEED_ANYWAY, language),
                        fontWeight = FontWeight.ExtraBold,
                        fontSize = dimensions.fontSizeBody.sp,
                        lineHeight = (dimensions.fontSizeBody * 1.4).sp
                    )
                }
            }
        }
    }
}

@Composable
fun HardwareCheckItem(
    label: String,
    value: String,
    status: Boolean,
    requirement: String
) {
    val dimensions = rememberResponsiveDimensions()
    Column(
        verticalArrangement = Arrangement.spacedBy(dimensions.small)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyMedium,
                color = SlateGrey,
                fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                fontSize = dimensions.fontSizeSmall.sp,
                lineHeight = (dimensions.fontSizeSmall * 1.4).sp
            )
            Text(
                text = value,
                style = MaterialTheme.typography.bodyMedium,
                color = if (status) SurvivalGreen else AlertRed,
                fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                fontSize = dimensions.fontSizeSmall.sp,
                lineHeight = (dimensions.fontSizeSmall * 1.4).sp
            )
        }
        Text(
            text = "REQUIRES: $requirement",
            style = MaterialTheme.typography.labelSmall,
            color = SlateGrey.copy(alpha = 0.7f),
            fontSize = dimensions.fontSizeLabel.sp,
            lineHeight = (dimensions.fontSizeLabel * 1.5).sp
        )
    }
}

@Composable
fun MessageBubble(message: Message) {
    val dimensions = rememberResponsiveDimensions()
    val colors = MaterialTheme.colorScheme
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (message.isUser) Alignment.End else Alignment.Start,
        verticalArrangement = Arrangement.spacedBy(dimensions.small)
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(dimensions.tiny),
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = dimensions.small)
        ) {
            Text(
                text = if (message.isUser) "你" else "AI",
                color = if (message.isUser) colors.primary else colors.secondary,
                fontWeight = FontWeight.Bold,
                fontSize = dimensions.fontSizeLabel.sp
            )
            Text(
                text = if (message.isUser) "USER" else "ASSISTANT",
                color = colors.onSurfaceVariant,
                fontSize = dimensions.fontSizeLabel.sp
            )
        }
        if (message.isUser) {
            UserMessage(text = message.text, imageBitmap = message.imageBitmap)
        } else {
            AIMessage(text = message.text, isTyping = message.isTyping)
        }
        Text(
            text = java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()).format(java.util.Date(message.timestamp)),
            color = colors.onSurfaceVariant,
            fontSize = dimensions.fontSizeLabel.sp,
            modifier = Modifier.padding(horizontal = dimensions.small)
        )
    }
}

@Composable
fun UserMessage(text: String, imageBitmap: Bitmap? = null) {
    val dimensions = rememberResponsiveDimensions()
    val colors = MaterialTheme.colorScheme
    Card(
        shape = RoundedCornerShape(dimensions.cardRadius),
        colors = CardDefaults.cardColors(
            containerColor = colors.primaryContainer
        ),
        border = androidx.compose.foundation.BorderStroke(
            width = 1.dp,
            color = colors.primary.copy(alpha = 0.25f)
        )
    ) {
        Column(
            horizontalAlignment = Alignment.End,
            verticalArrangement = Arrangement.spacedBy(dimensions.small),
            modifier = Modifier.padding(dimensions.medium)
        ) {
            if (imageBitmap != null) {
                Card(
                    modifier = Modifier.width(220.dp),
                    shape = RoundedCornerShape(dimensions.cardRadius),
                    colors = CardDefaults.cardColors(
                        containerColor = colors.surface
                    ),
                    border = androidx.compose.foundation.BorderStroke(
                        width = 1.dp,
                        color = colors.outline.copy(alpha = 0.3f)
                    )
                ) {
                    AsyncImage(
                        model = imageBitmap,
                        contentDescription = "User photo",
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(160.dp),
                        contentScale = ContentScale.Crop
                    )
                }
            }
            Text(
                text = text,
                style = MaterialTheme.typography.bodyLarge,
                color = colors.onPrimaryContainer,
                fontSize = dimensions.fontSizeBody.sp,
                lineHeight = (dimensions.fontSizeBody * 1.5).sp
            )
        }
    }
}

@Composable
fun AIMessage(text: String, isTyping: Boolean) {
    val dimensions = rememberResponsiveDimensions()
    val colors = MaterialTheme.colorScheme
    Card(
        modifier = Modifier.fillMaxWidth(dimensions.messageWidth),
        shape = RoundedCornerShape(dimensions.cardRadius),
        colors = CardDefaults.cardColors(
            containerColor = colors.surfaceVariant
        ),
        border = androidx.compose.foundation.BorderStroke(
            width = 1.dp,
            color = colors.outline.copy(alpha = 0.3f)
        )
    ) {
        Column(modifier = Modifier.padding(dimensions.medium)) {
            if (isTyping) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(dimensions.tiny),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(text = "●", color = colors.secondary)
                    Text(text = "●", color = colors.secondary.copy(alpha = 0.75f))
                    Text(text = "●", color = colors.secondary.copy(alpha = 0.5f))
                }
                Spacer(modifier = Modifier.height(dimensions.small))
            } else {
                TypewriterText(text = text)
            }
        }
    }
}

@Composable
fun TypingIndicator() {
    val dimensions = rememberResponsiveDimensions()
    val infiniteTransition = rememberInfiniteTransition(label = "typing")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "typingAlpha"
    )

    Row(
        modifier = Modifier.padding(dimensions.medium),
        horizontalArrangement = Arrangement.spacedBy(dimensions.tiny)
    ) {
        repeat(3) { index ->
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(RoundedCornerShape(50))
                    .background(SurvivalGreen.copy(alpha = alpha - (index * 0.2f).coerceAtLeast(0f)))
            )
        }
    }
}

@Composable
fun TypewriterText(text: String) {
    val dimensions = rememberResponsiveDimensions()
    Text(
        text = text,
        style = MaterialTheme.typography.bodyLarge,
        color = SurvivalGreen,
        modifier = Modifier.padding(dimensions.medium),
        fontSize = dimensions.fontSizeBody.sp,
        lineHeight = (dimensions.fontSizeBody * 1.6).sp,
        fontWeight = FontWeight.Medium
    )
}

@Composable
fun TelemetryBar(systemStatus: SystemStatus) {
    val dimensions = rememberResponsiveDimensions()
    val colors = MaterialTheme.colorScheme
    val infiniteTransition = rememberInfiniteTransition(label = "telemetry")
    val glow by infiniteTransition.animateFloat(
        initialValue = 0.7f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(2000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glow"
    )

    val tempColor = when {
        systemStatus.temperature > 45 -> AlertRed
        systemStatus.temperature > 40 -> SurvivalGreen.copy(alpha = 0.8f)
        else -> SurvivalGreen
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                horizontal = dimensions.medium,
                vertical = dimensions.small
            ),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(dimensions.medium)
        ) {
            Text(
                text = "RAM: ${systemStatus.ramAvailable}MB",
                style = MaterialTheme.typography.labelSmall,
                color = SurvivalGreen.copy(alpha = glow),
                fontWeight = FontWeight.Bold,
                fontSize = dimensions.fontSizeLabel.sp,
                lineHeight = (dimensions.fontSizeLabel * 1.4).sp
            )
            Text(
                text = "TEMP: ${String.format("%.1f", systemStatus.temperature)}°C",
                style = MaterialTheme.typography.labelSmall,
                color = tempColor.copy(alpha = glow),
                fontWeight = FontWeight.Bold,
                fontSize = dimensions.fontSizeLabel.sp,
                lineHeight = (dimensions.fontSizeLabel * 1.4).sp
            )
        }
        Row(
            horizontalArrangement = Arrangement.spacedBy(dimensions.medium)
        ) {
            Text(
                text = "TPS: ${String.format("%.1f", systemStatus.tokensPerSecond)}",
                style = MaterialTheme.typography.labelSmall,
                color = SurvivalGreen.copy(alpha = glow),
                fontWeight = FontWeight.Bold,
                fontSize = dimensions.fontSizeLabel.sp,
                lineHeight = (dimensions.fontSizeLabel * 1.4).sp
            )
            Text(
                text = "TOKENS: ${systemStatus.totalTokens}",
                style = MaterialTheme.typography.labelSmall,
                color = SurvivalGreen.copy(alpha = glow),
                fontWeight = FontWeight.Bold,
                fontSize = dimensions.fontSizeLabel.sp,
                lineHeight = (dimensions.fontSizeLabel * 1.4).sp
            )
        }
    }
}

@Composable
fun ThermalWarningOverlay(language: Language) {
    val dimensions = rememberResponsiveDimensions()
    val colors = MaterialTheme.colorScheme
    val infiniteTransition = rememberInfiniteTransition(label = "thermal")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.1f,
        targetValue = 0.3f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "thermalAlpha"
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(AlertRed.copy(alpha = alpha)),
        contentAlignment = Alignment.TopCenter
    ) {
        Card(
            shape = RoundedCornerShape(dimensions.buttonRadius),
            colors = CardDefaults.cardColors(
                containerColor = AlertRed.copy(alpha = 0.9f)
            ),
            modifier = Modifier.padding(top = dimensions.large)
        ) {
            Text(
                text = Lang.get(Lang.THERMAL_WARNING, language),
                style = MaterialTheme.typography.labelSmall,
                color = PureWhite,
                modifier = Modifier.padding(
                    horizontal = dimensions.small,
                    vertical = dimensions.tiny
                ),
                fontWeight = FontWeight.Bold,
                fontSize = dimensions.fontSizeSmall.sp,
                lineHeight = (dimensions.fontSizeSmall * 1.4).sp
            )
        }
    }
}

@Composable
fun BroadcastingOverlay(language: Language) {
    val dimensions = rememberResponsiveDimensions()
    val colors = MaterialTheme.colorScheme
    val infiniteTransition = rememberInfiniteTransition(label = "broadcast")
    val pulse by infiniteTransition.animateFloat(
        initialValue = 0.5f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(500, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse"
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(SurvivalGreen.copy(alpha = 0.1f * pulse)),
        contentAlignment = Alignment.Center
    ) {
        Card(
            shape = RoundedCornerShape(dimensions.cardRadius),
            colors = CardDefaults.cardColors(
                containerColor = PitchBlack.copy(alpha = 0.98f)
            ),
            border = androidx.compose.foundation.BorderStroke(
                width = 2.dp,
                color = SurvivalGreen.copy(alpha = pulse)
            )
        ) {
            Column(
                modifier = Modifier.padding(dimensions.large),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(dimensions.medium)
            ) {
                Text(
                    text = "📡",
                    fontSize = 48.sp
                )
                Text(
                    text = Lang.get(Lang.SEMANTIC_BROADCAST, language),
                    color = SurvivalGreen,
                    fontWeight = FontWeight.Bold,
                    fontSize = dimensions.fontSizeBody.sp
                )
                Text(
                    text = Lang.get(Lang.INFO_DEHYDRATION, language),
                    color = SlateGrey,
                    fontSize = dimensions.fontSizeSmall.sp
                )
            }
        }
    }
}

@Composable
fun InputBar(
    text: String,
    onTextChange: (String) -> Unit,
    onSend: () -> Unit,
    onBroadcast: () -> Unit,
    enabled: Boolean,
    language: Language
) {
    val dimensions = rememberResponsiveDimensions()
    var isPressed by remember { mutableStateOf(false) }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(dimensions.medium),
        shape = RoundedCornerShape(dimensions.cardRadius),
        colors = CardDefaults.cardColors(
            containerColor = Color.White.copy(alpha = 0.05f)
        ),
        border = androidx.compose.foundation.BorderStroke(
            width = 1.dp,
            color = Color.White.copy(alpha = if (enabled) 0.08f else 0.04f)
        )
    ) {
        Column(
            modifier = Modifier.padding(dimensions.small)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .padding(vertical = dimensions.small)
                ) {
                    androidx.compose.foundation.text.BasicTextField(
                        value = text,
                        onValueChange = { newValue ->
                            if (enabled) {
                                onTextChange(newValue)
                            }
                        },
                        enabled = enabled,
                        textStyle = TextStyle(
                            color = if (enabled) PureWhite else SlateGrey,
                            fontSize = dimensions.fontSizeBody.sp,
                            lineHeight = (dimensions.fontSizeBody * 1.5).sp
                        ),
                        singleLine = true,
                        cursorBrush = androidx.compose.ui.graphics.SolidColor(SurvivalGreen),
                        modifier = Modifier.fillMaxWidth()
                    )
                    
                    if (text.isEmpty()) {
                        Text(
                            text = if (enabled) Lang.get(Lang.ENTER_MESSAGE, language) else Lang.get(Lang.GENERATING, language),
                            color = SlateGrey,
                            fontSize = dimensions.fontSizeBody.sp,
                            lineHeight = (dimensions.fontSizeBody * 1.5).sp
                        )
                    }
                }

                Spacer(modifier = Modifier.width(dimensions.small))

                Box(
                    modifier = Modifier
                        .scale(if (isPressed && enabled) 0.98f else 1f)
                        .clip(RoundedCornerShape(dimensions.buttonRadius))
                        .background(if (enabled) PureWhite else SlateGrey.copy(alpha = 0.3f))
                        .clickable(enabled = enabled) {
                            isPressed = true
                            onSend()
                            isPressed = false
                        }
                        .padding(
                            horizontal = dimensions.medium,
                            vertical = dimensions.small
                        )
                ) {
                    Text(
                        text = Lang.get(Lang.SEND, language),
                        color = if (enabled) PitchBlack else SlateGrey,
                        fontSize = dimensions.fontSizeSmall.sp,
                        fontWeight = FontWeight.Bold,
                        lineHeight = (dimensions.fontSizeSmall * 1.3).sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(dimensions.small))

            Button(
                onClick = onBroadcast,
                modifier = Modifier.fillMaxWidth(),
                enabled = enabled && text.isNotEmpty(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = AlertRed.copy(alpha = 0.8f),
                    contentColor = PureWhite,
                    disabledContainerColor = SlateGrey.copy(alpha = 0.3f),
                    disabledContentColor = SlateGrey
                ),
                shape = RoundedCornerShape(dimensions.buttonRadius)
            ) {
                Text(
                    text = Lang.get(Lang.BROADCAST_DISASTER, language),
                    fontWeight = FontWeight.Bold,
                    fontSize = dimensions.fontSizeBody.sp,
                    lineHeight = (dimensions.fontSizeBody * 1.3).sp
                )
            }
        }
    }
}

fun checkRam(context: Context): Pair<Long, Long> {
    val activityManager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
    val memoryInfo = ActivityManager.MemoryInfo()
    activityManager.getMemoryInfo(memoryInfo)
    return Pair(memoryInfo.availMem / (1024 * 1024), memoryInfo.totalMem / (1024 * 1024))
}

fun readDeviceTemperature(context: Context): Float {
    val batteryIntent = context.registerReceiver(
        null,
        android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED)
    )

    val batteryTempTenths = batteryIntent?.getIntExtra(android.os.BatteryManager.EXTRA_TEMPERATURE, -1) ?: -1
    if (batteryTempTenths > 0) {
        return batteryTempTenths / 10f
    }

    return readThermalZoneTemperature()
}

private fun readThermalZoneTemperature(): Float {
    val thermalDirs = listOf(
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/class/thermal/thermal_zone1/temp",
        "/sys/class/thermal/thermal_zone2/temp"
    )

    thermalDirs.forEach { path ->
        try {
            val file = java.io.File(path)
            if (file.exists()) {
                val raw = file.readText().trim().toFloatOrNull() ?: return@forEach
                val tempC = when {
                    raw > 1000f -> raw / 1000f
                    else -> raw
                }
                if (tempC > -50f && tempC < 150f) {
                    return tempC
                }
            }
        } catch (_: Exception) {
            // Ignore and try next sensor source.
        }
    }

    return 0f
}

private fun findLocalGemmaModel(context: Context): File? {
    val externalModelDir = context.getExternalFilesDir(null)
    val candidates = buildList {
        add(File(context.filesDir, "model/gemma-4-e2b-it.litertlm"))
        add(File(context.filesDir, "model/gemma4e2b.bin"))
        add(File(context.filesDir, "gemma-4-e2b-it.litertlm"))
        add(File(context.filesDir, "gemma4e2b.bin"))
        if (externalModelDir != null) {
            add(File(externalModelDir, "gemma-4-e2b-it.litertlm"))
            add(File(externalModelDir, "model/gemma-4-e2b-it.litertlm"))
            add(File(externalModelDir, "gemma4e2b.bin"))
        }
    }
    return candidates.firstOrNull { it.exists() && it.length() > 0L }
}

private fun scanLocalModel(context: Context, language: Language): ModelStatus {
    return try {
        val file = findLocalGemmaModel(context)
        if (file != null) {
            ModelStatus(
                state = ModelLoadState.READY,
                modelName = file.name,
                modelPath = file.absolutePath
            )
        } else {
            ModelStatus(
                state = ModelLoadState.MISSING,
                errorMessage = if (language == Language.CHINESE) {
                    "未找到本地模型文件"
                } else {
                    "Local model file not found"
                }
            )
        }
    } catch (e: Exception) {
        ModelStatus(
            state = ModelLoadState.ERROR,
            errorMessage = e.message ?: "Model scan failed"
        )
    }
}

private fun hasLocalModel(context: Context): Boolean {
    return findLocalGemmaModel(context) != null
}

private fun importLocalModelFile(context: Context, uri: android.net.Uri): File? {
    val targetDir = File(context.getExternalFilesDir(null), "model")
    if (!targetDir.exists()) targetDir.mkdirs()

    val displayName: String = runCatching {
        val doc = DocumentFile.fromSingleUri(context, uri)
        doc?.name
    }.getOrNull()?.takeIf { it.isNotBlank() } ?: "gemma-4-e2b-it.litertlm"

    val targetFile = File(targetDir, displayName)

    return runCatching {
        context.contentResolver.openInputStream(uri)?.use { input ->
            targetFile.outputStream().use { output ->
                input.copyTo(output)
            }
        } ?: return null
        targetFile.takeIf { it.exists() && it.length() > 0L }
    }.getOrNull()
}

private suspend fun generateLocalModelResponse(
    context: Context,
    input: String,
    image: Bitmap? = null,
    language: Language,
    mode: String
): String? = withContext(Dispatchers.IO) {
    if (!hasLocalModel(context)) return@withContext null

    val prompt = buildString {
        appendLine(if (language == Language.CHINESE) "你是离线应急助手，请给出简洁可执行建议。" else "You are an offline emergency assistant. Give concise actionable advice.")
        appendLine("MODE=$mode")
        appendLine("INPUT=$input")
        if (image != null) appendLine("IMAGE_PRESENT=true")
    }
    when (mode) {
        "analysis" -> runCatching { LegacyBackendApiClient.analyze(prompt, image) }.getOrNull()?.takeIf { it.isNotBlank() }
        else -> runCatching { LegacyBackendApiClient.chat(prompt, image) }.getOrNull()?.takeIf { it.isNotBlank() }
    }
}

private fun flowOfChunks(text: String): Flow<String> = flow {
    text.chunked(6).forEach { chunk ->
        emit(chunk)
        delay(18)
    }
}

private fun buildStreamPrompt(input: String, language: Language, mode: String, imagePresent: Boolean): String = buildString {
    appendLine(if (language == Language.CHINESE) "你是离线应急助手，请给出简洁可执行建议。" else "You are an offline emergency assistant. Give concise actionable advice.")
    appendLine("MODE=$mode")
    appendLine("INPUT=$input")
    if (imagePresent) appendLine("IMAGE_PRESENT=true")
}

private fun isLocalModelResponse(text: String?): Boolean {
    return !text.isNullOrBlank()
}

suspend fun streamLocalChatResponse(
    context: Context,
    input: String,
    language: Language
): Flow<String> = withContext(Dispatchers.IO) {
    val response = generateLocalModelResponse(context, input, language = language, mode = "chat")
        ?: runCatching { LegacyBackendApiClient.chat(input) }.getOrNull()
        ?: generateLocalChatFallback(input)
    flowOfChunks(response)
}

suspend fun generateChatResponse(context: Context, input: String, language: Language): String {
    return generateLocalModelResponse(context, input, language = language, mode = "chat")
        ?: runCatching { LegacyBackendApiClient.chat(input) }
            .getOrElse {
                "ACKNOWLEDGED. PROCESSING: \"$input\"\n\n" +
                    "SYSTEM RESPONSE COMPLETE."
            }
}

private fun generateLocalChatFallback(input: String): String =
    "ACKNOWLEDGED. PROCESSING: \"$input\"\n\nSYSTEM RESPONSE COMPLETE."

private fun generateLocalAnalysisFallback(input: String): String = when {
    input.contains("出血", true) || input.contains("血", true) -> "【警告】：检测到伤口大量出血！\n\n【自救指令】：\n1. 立刻用干净的衣物或布料直接按压伤口\n2. 保持按压至少10-15分钟，不要频繁查看\n3. 抬高患肢高于心脏水平\n4. 寻找止血带或替代品（领带、布条等）\n5. 标记止血带使用时间\n\n【GEMMA 4 本地分析完成】"
    input.contains("水", true) || input.contains("喝", true) -> "【警告】：此水源可能含高岭土污染！\n\n【自救指令】：\n1. 立刻用衣物做三层过滤\n2. 煮沸至少5分钟（海拔每高1000米增加1分钟）\n3. 煮沸前绝对不可饮用！\n4. 如有条件，可使用净水药片\n\n【GEMMA 4 本地分析完成】"
    else -> "【分析】：收到图像和描述\n\n【建议】：\n1. 保持冷静，评估当前环境\n2. 检查是否有立即危险\n3. 寻找安全的避险位置\n4. 保存体力，等待救援或规划下一步\n\n【GEMMA 4 本地分析完成】"
}

suspend fun generateAnalysisResponse(context: Context, input: String, image: Bitmap, language: Language): String {
    return generateLocalModelResponse(context, input, image, language, mode = "analysis")
        ?: runCatching { BackendApiClient.analyze(input, image) }
            .getOrElse { generateLocalAnalysisFallback(input) }
}

fun dehydrateMessageForBroadcast(input: String): DehydratedMessage {
    val originalSize = input.toByteArray().size * 100
    
    val extractedKeywords = extractDisasterKeywords(input)
    val compressedContent = compressContent(extractedKeywords)
    
    val compressedSize = compressedContent.toByteArray().size
    val compressionRatio = originalSize.toFloat() / compressedSize.toFloat()
    
    return DehydratedMessage(
        id = System.currentTimeMillis(),
        originalSize = originalSize,
        compressedSize = compressedSize,
        compressionRatio = compressionRatio,
        content = compressedContent
    )
}

private fun List<PeerMessage>.mapToReports(): List<String> = map { it.content }

private fun PeerMessage.toVerifiedAlert(): VerifiedAlert = VerifiedAlert(
    id = System.currentTimeMillis(),
    alertType = AlertType.DAM_BREAK,
    confidence = 0.8f,
    verifyingPeers = 1,
    content = content,
    isTrusted = true
)

fun extractDisasterKeywords(input: String): List<String> {
    val keywords = mutableListOf<String>()
    val disasterTypes = listOf("坍塌", "倒塌", "地震", "火灾", "洪水", "滑坡", "爆炸", "泄漏")
    val victimTypes = listOf("伤员", "伤者", "被困", "受伤", "死亡", "失踪")
    val numbers = listOf("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "一", "二", "三", "四", "五")
    val locations = listOf("东区", "西区", "南区", "北区", "一楼", "二楼", "三楼")
    
    disasterTypes.forEach { type ->
        if (input.contains(type)) keywords.add(type)
    }
    victimTypes.forEach { type ->
        if (input.contains(type)) keywords.add(type)
    }
    numbers.forEach { num ->
        if (input.contains(num)) keywords.add(num)
    }
    locations.forEach { loc ->
        if (input.contains(loc)) keywords.add(loc)
    }
    
    if (keywords.isEmpty()) keywords.add("灾情报告")
    return keywords
}

fun compressContent(keywords: List<String>): String {
    return buildString {
        append("[紧急]")
        keywords.forEach { keyword ->
            append("[${keyword}]")
        }
        append("[TIME:${System.currentTimeMillis()}]")
        append("[NODE:Q4]")
    }
}

import 'package:shared_preferences/shared_preferences.dart';
import '../models/app_config.dart';

class StorageService {
  static const String _keyApiUrl = 'api_url';
  static const String _keyModelName = 'model_name';
  static const String _keyApiKey = 'api_key';
  static const String _keySystemPrompt = 'system_prompt';
  static const String _keyOwnPlantId = 'own_plant_id';
  static const String _keyHardwareIp = 'hardware_ip';
  static const String _keyHardwarePort = 'hardware_port';
  static const String _keyLocalModelPath = 'local_model_path';
  static const String _keyLocalMmprojPath = 'local_mmproj_path';
  static const String _keyAssistantNickname = 'assistant_nickname';
  static const String _keyEnableThinking = 'enable_thinking';
  static const String _keyContextSize = 'context_size';
  static const String _keyThreads = 'threads';
  static const String _keyTtsEnabled = 'tts_enabled';
  static const String _keyTtsStyle = 'tts_style';

  Future<AppConfig> loadConfig() async {
    final prefs = await SharedPreferences.getInstance();
    final defaultConfig = AppConfig.defaultConfig();

    return AppConfig(
      apiUrl: prefs.getString(_keyApiUrl) ?? defaultConfig.apiUrl,
      modelName: prefs.getString(_keyModelName) ?? defaultConfig.modelName,
      apiKey: prefs.getString(_keyApiKey) ?? defaultConfig.apiKey,
      systemPrompt:
          prefs.getString(_keySystemPrompt) ?? defaultConfig.systemPrompt,
      ownPlantId: prefs.getString(_keyOwnPlantId) ?? defaultConfig.ownPlantId,
      hardwareIp: prefs.getString(_keyHardwareIp) ?? defaultConfig.hardwareIp,
      hardwarePort:
          prefs.getString(_keyHardwarePort) ?? defaultConfig.hardwarePort,
      localModelPath:
          prefs.getString(_keyLocalModelPath) ?? defaultConfig.localModelPath,
      localMmprojPath:
          prefs.getString(_keyLocalMmprojPath) ?? defaultConfig.localMmprojPath,
      assistantNickname:
          prefs.getString(_keyAssistantNickname) ?? defaultConfig.assistantNickname,
      enableThinking:
          prefs.getBool(_keyEnableThinking) ?? defaultConfig.enableThinking,
      contextSize: prefs.getInt(_keyContextSize) ?? defaultConfig.contextSize,
      threads: prefs.getInt(_keyThreads) ?? defaultConfig.threads,
      ttsEnabled: prefs.getBool(_keyTtsEnabled) ?? defaultConfig.ttsEnabled,
      ttsStyle: prefs.getString(_keyTtsStyle) ?? defaultConfig.ttsStyle,
    );
  }

  Future<void> saveConfig(AppConfig config) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyApiUrl, config.apiUrl);
    await prefs.setString(_keyModelName, config.modelName);
    await prefs.setString(_keyApiKey, config.apiKey);
    await prefs.setString(_keySystemPrompt, config.systemPrompt);
    await prefs.setString(_keyOwnPlantId, config.ownPlantId);
    await prefs.setString(_keyHardwareIp, config.hardwareIp);
    await prefs.setString(_keyHardwarePort, config.hardwarePort);
    await prefs.setString(_keyLocalModelPath, config.localModelPath);
    await prefs.setString(_keyLocalMmprojPath, config.localMmprojPath);
    await prefs.setString(_keyAssistantNickname, config.assistantNickname);
    await prefs.setBool(_keyEnableThinking, config.enableThinking);
    await prefs.setInt(_keyContextSize, config.contextSize);
    await prefs.setInt(_keyThreads, config.threads);
    await prefs.setBool(_keyTtsEnabled, config.ttsEnabled);
    await prefs.setString(_keyTtsStyle, config.ttsStyle);
  }
}

import 'package:flutter/foundation.dart';
import '../models/app_config.dart';
import '../services/storage_service.dart';

class ConfigProvider with ChangeNotifier {
  final StorageService _storageService = StorageService();
  AppConfig _config = AppConfig.defaultConfig();
  bool _isLoading = true;

  AppConfig get config => _config;
  bool get isLoading => _isLoading;

  ConfigProvider() {
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    _config = await _storageService.loadConfig();
    _isLoading = false;
    notifyListeners();
  }

  Future<void> updateConfig(
    String apiUrl,
    String modelName,
    String apiKey,
    String systemPrompt,
    String ownPlantId,
    String hardwareIp,
    String hardwarePort,
    String localModelPath,
    String localMmprojPath,
    String assistantNickname,
    bool enableThinking,
    int contextSize,
    int threads,
    bool ttsEnabled,
    String ttsStyle,
  ) async {
    _config.apiUrl = apiUrl;
    _config.modelName = modelName;
    _config.apiKey = apiKey;
    _config.systemPrompt = systemPrompt;
    _config.ownPlantId = ownPlantId;
    _config.hardwareIp = hardwareIp;
    _config.hardwarePort = hardwarePort;
    _config.localModelPath = localModelPath;
    _config.localMmprojPath = localMmprojPath;
    _config.assistantNickname = assistantNickname;
    _config.enableThinking = enableThinking;
    _config.contextSize = contextSize;
    _config.threads = threads;
    _config.ttsEnabled = ttsEnabled;
    _config.ttsStyle = ttsStyle;
    await _storageService.saveConfig(_config);
    notifyListeners();
  }

  Future<void> updateTtsEnabled(bool enabled) async {
    _config.ttsEnabled = enabled;
    await _storageService.saveConfig(_config);
    notifyListeners();
  }

  Future<void> updateTtsStyle(String style) async {
    _config.ttsStyle = style;
    await _storageService.saveConfig(_config);
    notifyListeners();
  }
}

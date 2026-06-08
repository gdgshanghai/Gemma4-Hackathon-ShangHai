class AppConfig {
  String apiUrl;
  String modelName;
  String apiKey;
  String systemPrompt;
  String ownPlantId;
  String hardwareIp;
  String hardwarePort;
  String localModelPath;
  String localMmprojPath;
  bool enableThinking;
  int contextSize;
  int threads;
  String assistantNickname;
  bool ttsEnabled;
  String ttsStyle;

  AppConfig({
    required this.apiUrl,
    required this.modelName,
    required this.apiKey,
    required this.systemPrompt,
    required this.ownPlantId,
    required this.hardwareIp,
    required this.hardwarePort,
    required this.localModelPath,
    required this.localMmprojPath,
    required this.assistantNickname,
    required this.enableThinking,
    required this.contextSize,
    required this.threads,
    required this.ttsEnabled,
    required this.ttsStyle,
  });

  // 提交版本默认不内置任何隐私或局域网信息，首次运行后由评委手动填写。
  factory AppConfig.defaultConfig() {
    return AppConfig(
      apiUrl: '',
      modelName: 'gemma-4-E2B-it-GGUF',
      apiKey: '',
      systemPrompt:
          '你是一个运行在端侧 Gemma 4 多模态模型上的智能植物助手。'
          '你会结合植物图像、传感器状态和历史记忆，用简体中文给出自然、温柔、简洁的回应。',
      ownPlantId: 'pothos_warm',
      hardwareIp: '',
      hardwarePort: '80',
      localModelPath: '',
      localMmprojPath: '',
      assistantNickname: 'Gemma 小植',
      enableThinking: false,
      contextSize: 4096,
      threads: 6,
      ttsEnabled: false,
      ttsStyle: 'M1',
    );
  }
}

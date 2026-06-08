import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:llamadart/llamadart.dart';
import '../models/app_config.dart';
import '../models/message.dart';
import '../models/planter_data.dart';
import '../models/plant_friend.dart';
import '../services/api_service.dart';
import '../services/local_llama_service.dart';
import '../services/local_model_coordinator.dart';
import '../services/planter_service.dart';
import 'memory_provider.dart';
import 'tree_hole_provider.dart';

class ChatProvider with ChangeNotifier {
  static const String assistantConversationId = 'assistant';

  final ApiService _apiService = ApiService();
  final LocalLlamaService _localLlamaService = LocalLlamaService();
  final PlanterService _planterService = PlanterService();
  final Map<String, List<Message>> _conversationMessages = {
    assistantConversationId: <Message>[],
  };
  bool _isTyping = false;
  bool _isModelLoading = false;
  bool _hasPreparedStartupGreeting = false;
  bool _isPreparingStartupGreeting = false;
  String _currentLoadedModelPath = '';
  String _currentLoadedMmprojPath = '';
  String _activeConversationId = assistantConversationId;
  String? _lastErrorLog;

  AppConfig _config = AppConfig.defaultConfig();
  MemoryProvider? _memoryProvider;

  void setMemoryProvider(MemoryProvider memoryProvider) {
    _memoryProvider = memoryProvider;
  }

  Future<void> preloadModel() async {
    if (_isModelLoading) return;
    if (_config.localModelPath.trim().isEmpty) return;
    if (_currentLoadedModelPath == _config.localModelPath &&
        _currentLoadedMmprojPath == _config.localMmprojPath) {
      return;
    }

    _isModelLoading = true;
    notifyListeners();

    try {
      await LocalModelCoordinator.runChatTask(() async {
        await _ensureLocalModelReady(_config);
        debugPrint('模型预加载完成，构建 warmup messages...');

        final assistantName = _config.assistantNickname.trim().isNotEmpty
            ? _config.assistantNickname.trim()
            : 'AI 助手';
        final hasCustomPrompt = _config.systemPrompt.trim().isNotEmpty;

        final promptSb = StringBuffer();
        promptSb.write('你的名字是"$assistantName"。');
        promptSb.write('核心身份规则：你绝对不能透露自己是AI或任何大模型。你就是$assistantName。');
        if (hasCustomPrompt) {
          promptSb.write('角色设定：${_config.systemPrompt.trim()}');
        }
        promptSb.write('要求：私聊场景，回复要口语化自然简短。');
        promptSb.write('重要语言规则：你必须始终使用简体中文回复，禁止使用英文或其他语言。');

        final stopwatch = Stopwatch()..start();
        await for (final _ in _localLlamaService.generateResponse([
          LlamaChatMessage.fromText(role: LlamaChatRole.system, text: promptSb.toString()),
          LlamaChatMessage.fromText(role: LlamaChatRole.user, text: '你好呀，今天天气不错'),
          LlamaChatMessage.fromText(role: LlamaChatRole.assistant, text: '是呢，阳光挺好的。你呢，在干嘛？'),
          LlamaChatMessage.fromText(role: LlamaChatRole.user, text: '我在给植物浇水，你呢？'),
          LlamaChatMessage.fromText(role: LlamaChatRole.assistant, text: '哈哈我也刚浇完，植物们都精神了。'),
          LlamaChatMessage.fromText(role: LlamaChatRole.user, text: '好的，回头聊'),
        ])) {}
        stopwatch.stop();
        debugPrint('模型 warmup 完成，耗时 ${stopwatch.elapsedMilliseconds}ms');
      });
    } catch (e) {
      debugPrint('模型预加载失败: $e');
    } finally {
      _isModelLoading = false;
      notifyListeners();
    }
  }

  void clearAssistantMemory() {
    _memoryProvider?.clearMemory(_config.ownPlantId);
    _conversationMessages[assistantConversationId]?.clear();
    _hasPreparedStartupGreeting = false;
    notifyListeners();
  }

  void updateConfig(AppConfig config) {
    final oldPlantId = _config.ownPlantId;
    final oldPrompt = _config.systemPrompt.trim();
    final oldNick = _config.assistantNickname.trim();

    final identityChanged = oldPlantId != config.ownPlantId ||
        oldPrompt != config.systemPrompt.trim() ||
        oldNick != config.assistantNickname.trim();

    _config = config;

    if (identityChanged) {
      _memoryProvider?.clearMemory(oldPlantId);
      _conversationMessages[assistantConversationId]?.clear();
      _hasPreparedStartupGreeting = false;
    }

    _conversationMessages.putIfAbsent(
      assistantConversationId,
      () => <Message>[],
    );
    notifyListeners();
    if (_hasPreparedStartupGreeting &&
        config.localModelPath.trim().isNotEmpty &&
        _currentLoadedModelPath != config.localModelPath) {
      unawaited(preloadModel());
    }
  }

  String get activeConversationId => _activeConversationId;
  String get activePlantId => _activeConversationId == assistantConversationId
      ? _config.ownPlantId
      : _activeConversationId;
  bool get isTyping => _isTyping;
  bool get isModelLoading => _isModelLoading;
  String? get lastErrorLog => _lastErrorLog;
  List<Message> get messages => List.unmodifiable(
    _conversationMessages[_activeConversationId] ?? const [],
  );
  PlantProfile? get assistantPlantProfile => PlantCatalog.tryById(_config.ownPlantId);
  String get assistantDisplayName {
    final nickname = _config.assistantNickname.trim();
    if (nickname.isNotEmpty) {
      return nickname;
    }
    return 'AI 助手';
  }
  PlantProfile? get activePlantProfile =>
      _activeConversationId == assistantConversationId
      ? null
      : PlantCatalog.tryById(_activeConversationId);
  String get activeConversationTitle {
    if (_activeConversationId == assistantConversationId) {
      return assistantDisplayName;
    }
    return activePlantProfile?.name ?? assistantDisplayName;
  }

  void setActiveConversation(String conversationId) {
    _conversationMessages.putIfAbsent(conversationId, () => <Message>[]);
    _activeConversationId = conversationId;
    _lastErrorLog = null;
    notifyListeners();
  }

  List<Message> _messagesFor(String conversationId) {
    return _conversationMessages.putIfAbsent(conversationId, () => <Message>[]);
  }

  List<Message> _buildRequestMessages(AppConfig config, String conversationId) {
    final requestMessages = <Message>[];
    final activeProfile = conversationId == assistantConversationId
        ? PlantCatalog.tryById(config.ownPlantId)
        : PlantCatalog.tryById(conversationId);
    final assistantName = config.assistantNickname.trim().isNotEmpty
        ? config.assistantNickname.trim()
        : 'AI 助手';

    final memoryCtx = conversationId == assistantConversationId
        ? (_memoryProvider?.buildMemoryContext(config.ownPlantId) ?? '')
        : (_memoryProvider?.buildMemoryContext(conversationId) ?? '');

    final systemSections = <String>[];
    final hasCustomPrompt = config.systemPrompt.trim().isNotEmpty;

    if (conversationId == assistantConversationId) {
      if (hasCustomPrompt) {
        systemSections.addAll([
          '你的名字是"$assistantName"。',
          '核心身份规则：你绝对不能透露自己是AI、人工智能、语言模型或任何大模型（包括但不限于Gemma、LLaMA、Qwen、Claude、GPT等）。你就是$assistantName，不是任何AI程序。如果被问到身份，你必须坚持你的角色设定，不要提及任何技术术语。',
          '以下是你的角色设定，你必须严格遵守：',
          config.systemPrompt.trim(),
          '要求：这是私聊场景，不是朋友圈。回复要像熟人聊天，口语化、自然、简短。',
        ]);
      } else {
        systemSections.addAll([
          '你的名字是"$assistantName"。',
          '核心身份规则：你绝对不能透露自己是AI、人工智能、语言模型或任何大模型（包括但不限于Gemma、LLaMA、Qwen、Claude、GPT等）。如果被问到身份，你就是$assistantName，不要提及任何技术术语。',
          '要求：这是私聊场景，不是朋友圈。回复要像熟人聊天，口语化、自然、简短。',
        ]);
      }
    } else if (activeProfile != null) {
      systemSections.addAll([
        TreeHoleProvider.characterVoice(activeProfile),
        '核心身份规则：你绝对不能透露自己是AI、人工智能、语言模型或任何大模型（包括但不限于Gemma、LLaMA、Qwen、Claude、GPT等）。你就是${activeProfile.name}，一盆真实存在的、有灵魂的植物。如果被问到身份，你必须坚持你的植物人设，不要提及任何技术术语。',
        '要求：这是私聊场景，不是朋友圈。你就是一盆有灵魂的${activeProfile.name}，回复要像熟人聊天，口语化、自然、简短，持续保持该植物人设。',
      ]);
    } else if (hasCustomPrompt) {
      systemSections.addAll([
        '你的名字是"$assistantName"。',
        '核心身份规则：你绝对不能透露自己是AI、人工智能、语言模型或任何大模型（包括但不限于Gemma、LLaMA、Qwen、Claude、GPT等）。你就是$assistantName。',
        config.systemPrompt.trim(),
      ]);
    }

    if (memoryCtx.isNotEmpty) {
      systemSections.add(memoryCtx);
    }

    if (systemSections.isNotEmpty) {
      requestMessages.add(
        Message(
          role: 'system',
          content: systemSections.join('\n'),
          timestamp: DateTime.now(),
        ),
      );
    }

    final conversation = _messagesFor(conversationId);
    for (final msg in conversation) {
      if (msg.role == 'assistant' &&
          msg.content.isEmpty &&
          msg == conversation.last) {
        continue;
      }
      requestMessages.add(msg);
    }

    return requestMessages;
  }

  List<LlamaChatMessage> _buildLlamaMessages(
    List<Message> requestMessages,
  ) {
    final llamaMessages = <LlamaChatMessage>[];

    for (final message in requestMessages) {
      if (message.role == 'system') {
        llamaMessages.add(
          LlamaChatMessage.fromText(
            role: LlamaChatRole.system,
            text: message.content,
          ),
        );
        continue;
      }

      final role = message.role == 'assistant'
          ? LlamaChatRole.assistant
          : LlamaChatRole.user;

      final parts = <LlamaContentPart>[];
      if (message.content.trim().isNotEmpty) {
        parts.add(LlamaTextContent(message.content));
      }
      for (final imagePath in message.imagePaths) {
        parts.add(LlamaImageContent(path: imagePath));
      }

      llamaMessages.add(
        parts.isEmpty
            ? LlamaChatMessage.fromText(role: role, text: '')
            : LlamaChatMessage.withContent(role: role, content: parts),
      );
    }

    return llamaMessages;
  }

  Future<List<Map<String, dynamic>>> _buildApiMessages(
    List<Message> requestMessages,
  ) async {
    final result = <Map<String, dynamic>>[];
    for (final message in requestMessages) {
      if (message.imagePaths.isEmpty) {
        result.add({'role': message.role, 'content': message.content});
        continue;
      }

      final parts = <Map<String, dynamic>>[];
      if (message.content.trim().isNotEmpty) {
        parts.add({'type': 'text', 'text': message.content});
      }
      for (final imagePath in message.imagePaths) {
        final bytes = await File(imagePath).readAsBytes();
        final base64Image = base64Encode(bytes);
        parts.add({
          'type': 'image_url',
          'image_url': {'url': 'data:image/jpeg;base64,$base64Image'},
        });
      }
      result.add({'role': message.role, 'content': parts});
    }
    return result;
  }

  Future<void> _ensureLocalModelReady(AppConfig config) async {
    if (_currentLoadedModelPath == config.localModelPath &&
        _currentLoadedMmprojPath == config.localMmprojPath &&
        config.localModelPath.trim().isNotEmpty) {
      return;
    }

    await LocalModelCoordinator.ensureStoragePermissions();
    await _localLlamaService.dispose();
    await _localLlamaService.init(
      config.localModelPath,
      config.localMmprojPath,
      config.contextSize,
      config.threads,
      config.enableThinking,
    );
    _currentLoadedModelPath = config.localModelPath;
    _currentLoadedMmprojPath = config.localMmprojPath;
  }

  String _formatTemperature(double value) {
    final rounded = value.roundToDouble();
    if ((value - rounded).abs() < 0.05) {
      return rounded.toInt().toString();
    }
    return value.toStringAsFixed(1);
  }

  String _buildStartupGreetingPrompt(PlanterData data) {
    return '''
请你主动对主人说打开聊天页面后的第一句话。

这是你刚获取到的实时状态：
- 温度：${_formatTemperature(data.temperature)} 摄氏度
- 土壤湿度：${data.moisture}
- 情绪值：${data.emotion}
- 当前状态：${data.isSleeping ? '正在休眠' : '已经醒着'}
- 手动覆盖：${data.hasOverride ? '已开启' : '未开启'}

补充说明：
- 土壤湿度数值通常越大表示越湿润，只有明显偏低时才需要委婉提醒浇水。

回复要求：
1. 用第一人称，像植物本人在和主人私聊。
2. 先自然打招呼，再结合当前状态说感受和建议。
3. 回复控制在 1 到 3 句话，口语化、温柔、简短。
4. 只输出你要对主人说的话，不要解释规则，不要列点，不要提传感器或模型。
''';
  }

  Future<Stream<String>> _createResponseStream(
    AppConfig config,
    List<Message> requestMessages,
    Message aiMessage,
  ) async {
    if (config.localModelPath.trim().isNotEmpty) {
      if (_currentLoadedModelPath != config.localModelPath ||
          _currentLoadedMmprojPath != config.localMmprojPath) {
        aiMessage.content = '[正在请求存储权限并加载本地模型，请稍候...]';
        notifyListeners();
      }

      try {
        await _ensureLocalModelReady(config);
        aiMessage.content = '';
        notifyListeners();
        return _localLlamaService.generateResponse(
          _buildLlamaMessages(requestMessages),
        );
      } catch (e) {
        if (config.apiUrl.trim().isEmpty) {
          rethrow;
        }
        _lastErrorLog = '聊天本地模型异常：$e';
        aiMessage.content = '[本地模型不可用，正在切换到接口模型...]';
        notifyListeners();
        return _apiService.sendRawMessageStream(
          await _buildApiMessages(requestMessages),
          config,
        );
      }
    }

    if (config.apiUrl.trim().isNotEmpty) {
      return _apiService.sendRawMessageStream(
        await _buildApiMessages(requestMessages),
        config,
      );
    }

    throw Exception('未配置可用的大语言模型，请先配置本地模型或接口模型');
  }

  Future<void> _streamIntoMessage(
    Stream<String> stream,
    Message aiMessage,
    AppConfig config,
  ) async {
    await for (final chunk in stream) {
      aiMessage.content += chunk;
      notifyListeners();
    }
  }

  Future<void> prepareStartupAssistantGreeting(AppConfig config) async {
    if (_hasPreparedStartupGreeting || _isPreparingStartupGreeting) {
      return;
    }

    final conversation = _messagesFor(assistantConversationId);
    if (conversation.isNotEmpty) {
      _hasPreparedStartupGreeting = true;
      return;
    }

    _hasPreparedStartupGreeting = true;
    _isPreparingStartupGreeting = true;
    Message? startupMessage;

    try {
      final planterData = await _planterService.fetchPlanterData(config);
      if (conversation.isNotEmpty) {
        return;
      }

      startupMessage = Message(
        role: 'assistant',
        content: '',
        timestamp: DateTime.now(),
      );
      conversation.add(startupMessage);
      _isTyping = true;
      _lastErrorLog = null;
      notifyListeners();

      final requestMessages = _buildRequestMessages(
        config,
        assistantConversationId,
      )..add(
          Message(
            role: 'user',
            content: _buildStartupGreetingPrompt(planterData),
            timestamp: DateTime.now(),
          ),
        );

      await LocalModelCoordinator.runChatTask(() async {
        final stream = await _createResponseStream(
          config,
          requestMessages,
          startupMessage!,
        );
        await _streamIntoMessage(stream, startupMessage, config);
      });

      if (startupMessage.content.trim().isEmpty) {
        conversation.remove(startupMessage);
        await preloadModel();
      }
    } catch (e) {
      if (startupMessage != null) {
        conversation.remove(startupMessage);
      }
      debugPrint('启动问候生成失败，回退 warmup: $e');
      await preloadModel();
    } finally {
      _isTyping = false;
      _isPreparingStartupGreeting = false;
      notifyListeners();
    }
  }

  Future<void> sendMessage(
    String text,
    AppConfig config, {
    List<String> imagePaths = const [],
  }) async {
    if (text.trim().isEmpty && imagePaths.isEmpty) return;

    final conversationId = _activeConversationId;
    final conversation = _messagesFor(conversationId);

    final userMessage = Message(
      role: 'user',
      content: text,
      timestamp: DateTime.now(),
      imagePaths: imagePaths,
    );
    conversation.add(userMessage);
    notifyListeners();

    final aiMessage = Message(
      role: 'assistant',
      content: '',
      timestamp: DateTime.now(),
    );
    conversation.add(aiMessage);
    _isTyping = true;
    _lastErrorLog = null;
    notifyListeners();

    try {
      final requestMessages = _buildRequestMessages(config, conversationId);
      if (config.localModelPath.trim().isNotEmpty) {
        await LocalModelCoordinator.runChatTask(() async {
          final stream = await _createResponseStream(
            config,
            requestMessages,
            aiMessage,
          );
          await _streamIntoMessage(stream, aiMessage, config);
        });
      } else {
        final stream = await _createResponseStream(config, requestMessages, aiMessage);
        await _streamIntoMessage(stream, aiMessage, config);
      }
    } catch (e) {
      _lastErrorLog = '聊天生成失败：$e';
      aiMessage.content = '请求出错: $e';
      notifyListeners();
    } finally {
      _isTyping = false;
      notifyListeners();
      if (_memoryProvider != null && aiMessage.content.trim().isNotEmpty) {
        unawaited(_memoryProvider!.addChatMemory(
          conversationId,
          text,
          aiMessage.content,
          ownPlantId: config.ownPlantId,
          config: config,
        ));
      }
    }
  }

  void clearMessages() {
    _messagesFor(_activeConversationId).clear();
    notifyListeners();
  }

  @override
  void dispose() {
    unawaited(_localLlamaService.dispose());
    super.dispose();
  }
}

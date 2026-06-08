import 'package:flutter/foundation.dart';
import 'package:llamadart/llamadart.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/app_config.dart';
import '../services/local_llama_service.dart';
import '../services/local_model_coordinator.dart';

class MemoryProvider with ChangeNotifier {
  static const int _maxMemoryLength = 500;
  static const int _compressTargetLength = 100;
  static const String _memoryKeyPrefix = 'plant_memory_';

  final LocalLlamaService _localLlamaService = LocalLlamaService();
  final Map<String, String> _memories = {};
  final Set<String> _compressingPlants = {};
  String _currentLoadedModelPath = '';
  String _currentLoadedMmprojPath = '';

  String getMemory(String plantId) {
    return _memories[plantId] ?? '';
  }

  bool hasMemory(String plantId) {
    final m = _memories[plantId];
    return m != null && m.isNotEmpty;
  }

  Future<void> loadAllMemories() async {
    final prefs = await SharedPreferences.getInstance();
    final keys = prefs.getKeys().where((k) => k.startsWith(_memoryKeyPrefix));
    for (final key in keys) {
      final plantId = key.substring(_memoryKeyPrefix.length);
      final value = prefs.getString(key);
      if (value != null && value.isNotEmpty) {
        _memories[plantId] = value;
      }
    }
    notifyListeners();
  }

  Future<void> addMemory(
    String plantId,
    String content, {
    required String source,
    required AppConfig config,
  }) async {
    if (content.trim().isEmpty) return;

    while (_compressingPlants.contains(plantId)) {
      await Future.delayed(const Duration(milliseconds: 100));
    }

    final existing = _memories[plantId] ?? '';
    final newTotal = existing.isEmpty
        ? '[$source] $content'
        : '$existing\n[$source] $content';

    if (newTotal.length > _maxMemoryLength) {
      _compressingPlants.add(plantId);
      try {
        final compressed = await _summarizeAndCompress(plantId, existing, config);
        _memories[plantId] = compressed;
        await _saveMemory(plantId, compressed);

        final base = _memories[plantId] ?? '';
        final finalContent = base.isEmpty
            ? '[$source] $content'
            : '$base\n[$source] $content';
        _memories[plantId] = finalContent;
        await _saveMemory(plantId, finalContent);
      } finally {
        _compressingPlants.remove(plantId);
      }
      notifyListeners();
      return;
    }

    _memories[plantId] = newTotal;
    await _saveMemory(plantId, newTotal);
    notifyListeners();
  }

  Future<void> addChatMemory(
    String conversationId,
    String userContent,
    String assistantContent, {
    required String ownPlantId,
    required AppConfig config,
  }) async {
    final targetPlantId = conversationId == 'assistant'
        ? ownPlantId
        : conversationId;
    final summary = '用户：${_truncate(userContent, 80)}\n${_getPlantName(targetPlantId)}：${_truncate(assistantContent, 80)}';
    await addMemory(targetPlantId, summary, source: '私聊', config: config);
  }

  Future<void> addMomentMemory(
    String plantId, {
    required String postContent,
    String? commentContent,
    String? commenterName,
    required AppConfig config,
  }) async {
    final parts = <String>[];
    if (postContent.isNotEmpty) {
      parts.add('动态：${_truncate(postContent, 60)}');
    }
    if (commentContent != null && commentContent.isNotEmpty) {
      parts.add('${commenterName ?? '某人'}评论：${_truncate(commentContent, 60)}');
    }
    if (parts.isEmpty) return;
    await addMemory(plantId, parts.join(' | '), source: '朋友圈', config: config);
  }

  Future<void> clearMemory(String plantId) async {
    _memories.remove(plantId);
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('$_memoryKeyPrefix$plantId');
    notifyListeners();
  }

  Future<void> recordMomentPost(
    String plantId,
    String postContent, {
    AppConfig? config,
  }) async {
    if (postContent.trim().isEmpty) return;
    await _appendRaw(plantId, '[朋友圈] 发动态：${_truncate(postContent, 120)}');
  }

  Future<void> recordMomentComment({
    required String actorPlantId,
    required String targetOwnerPlantId,
    required String postAuthorName,
    required String actorName,
    required String commentContent,
    String? targetPostContent,
    AppConfig? config,
  }) async {
    if (commentContent.trim().isEmpty) return;
    final summary =
        '[朋友圈] ${actorName}评论了${postAuthorName}的动态：${_truncate(commentContent, 100)}';
    await _appendRaw(actorPlantId, summary);
    if (actorPlantId != targetOwnerPlantId) {
      await _appendRaw(targetOwnerPlantId, summary);
    }
  }

  Future<void> _appendRaw(String plantId, String summary) async {
    final existing = _memories[plantId] ?? '';
    final updated = existing.isEmpty ? summary : '$existing\n$summary';
    _memories[plantId] = updated;
    await _saveMemory(plantId, updated);
    notifyListeners();
  }

  Future<void> _saveMemory(String plantId, String content) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('$_memoryKeyPrefix$plantId', content);
  }

  Future<String> _summarizeAndCompress(
    String plantId,
    String memoryToCompress,
    AppConfig config,
  ) async {
    if (memoryToCompress.trim().isEmpty) return '';

    if (config.localModelPath.trim().isEmpty) {
      final truncated = memoryToCompress.length > _compressTargetLength
          ? '…${memoryToCompress.substring(memoryToCompress.length - _compressTargetLength)}'
          : memoryToCompress;
      return '[截断] $truncated';
    }

    try {
      final summarized = await LocalModelCoordinator.runBackgroundTaskOrSkip(() async {
        await _ensureLocalModelReady(config);

        final messages = [
          LlamaChatMessage.fromText(
            role: LlamaChatRole.system,
            text: '你是一个记忆总结助手。请将以下植物的互动记忆总结归纳为一段不超过${_compressTargetLength}字的摘要，保留关键信息（谁、做了什么、情感倾向）。直接输出总结内容，不要任何前缀或解释。',
          ),
          LlamaChatMessage.fromText(
            role: LlamaChatRole.user,
            text: '请总结以下记忆：\n$memoryToCompress',
          ),
        ];

        final buffer = StringBuffer();
        await for (final chunk in _localLlamaService.generateResponse(messages)) {
          buffer.write(chunk);
        }
        return buffer.toString().trim();
      });
      if (summarized == null) {
        throw Exception('聊天任务占用本地模型，已跳过本轮记忆压缩');
      }
      if (summarized.isNotEmpty && summarized.length <= _maxMemoryLength) {
        return '[总结] $summarized';
      }
    } catch (e) {
      debugPrint('记忆总结失败: $e');
    }

    final truncated = memoryToCompress.length > _compressTargetLength
        ? '…${memoryToCompress.substring(memoryToCompress.length - _compressTargetLength)}'
        : memoryToCompress;
    return '[截断] $truncated';
  }

  Future<void> _ensureLocalModelReady(AppConfig config) async {
    if (_currentLoadedModelPath == config.localModelPath &&
        _currentLoadedMmprojPath == config.localMmprojPath &&
        config.localModelPath.trim().isNotEmpty) {
      return;
    }

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

  String _truncate(String text, int maxLen) {
    if (text.length <= maxLen) return text;
    return '${text.substring(0, maxLen)}...';
  }

  String _getPlantName(String plantId) {
    if (plantId == 'assistant') return '助手';
    return plantId;
  }

  String buildMemoryContext(String plantId) {
    final memory = getMemory(plantId);
    if (memory.isEmpty) return '';
    return '【记忆背景】\n$memory';
  }
}

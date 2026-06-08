import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import '../models/app_config.dart';
import '../models/plant_friend.dart';
import 'local_llama_service.dart';
import 'local_model_coordinator.dart';

class RecognitionResult {
  final PlantProfile? profile;
  final bool isSuccess;
  final String? errorMessage;
  final String? rawResponse;
  final String? errorType;

  const RecognitionResult({
    this.profile,
    required this.isSuccess,
    this.errorMessage,
    this.rawResponse,
    this.errorType,
  });

  factory RecognitionResult.success(PlantProfile profile) {
    return RecognitionResult(profile: profile, isSuccess: true);
  }

  factory RecognitionResult.failure({
    required String errorMessage,
    required String errorType,
    String? rawResponse,
  }) {
    return RecognitionResult(
      isSuccess: false,
      errorMessage: errorMessage,
      errorType: errorType,
      rawResponse: rawResponse,
    );
  }
}

class PlantRecognitionService {
  static final PlantRecognitionService _instance =
      PlantRecognitionService._internal();
  factory PlantRecognitionService() => _instance;
  PlantRecognitionService._internal();

  final LocalLlamaService _localLlamaService = LocalLlamaService();
  String _currentLoadedModelPath = '';
  String _currentLoadedMmprojPath = '';

  static const String _systemPrompt = '''你是一个"植物灵魂鉴定师"。用户会给你一张植物的照片，你需要：
1. 识别照片中的植物种类
2. 根据这种植物的特性，赋予它一个独特、有趣的人格

你必须用严格的扁平JSON格式回复，禁止使用嵌套对象。不要包含任何其他文字，不要用markdown代码块包裹，不要用```json开头。直接输出JSON内容：
{
  "name": "植物名称（中文，带有性格前缀，如：傲娇仙人球、佛系多肉、话痨绿萝）",
  "tags": ["性格标签1", "性格标签2", "性格标签3"],
  "signature": "一句话个性签名（不超过40字，要有趣、有个性、符合植物特点）",
  "iconKey": "从下方图标列表中选一个最匹配的图标",
  "tone": "从下方性格列表中选一个最匹配的性格"
}

可选的iconKey（必须从中选择一个）：
{ICON_KEYS}

可选的tone（必须从中选择一个）：
- tsundere: 傲娇、嘴硬心软
- observer: 腹黑、冷幽默、静观其变
- cool: 高冷、极简、御姐
- zen: 佛系、养生、随缘
- reliable: 可靠、实用、话少
- warm: 温柔、老好人、元气
- princess: 娇贵、敏感、公主/千金
- sunshine: 阳光、自恋、大男孩
- stoic: 坚韧、钢铁直、抗压
- poetic: 浪漫、文艺、诗意
- money: 财迷、拜金、嘴甜
- dramatic: 抓马、情绪化、Drama Queen
- romantic: 恋爱脑、浪漫、娇气
- playful: 活泼、好玩、显眼包
- scholar: 学霸、严谨、高智商
- sharp: 毒舌、辣妹、叛逆

如果照片中没有植物或无法识别，请回复：{"error": "未能识别到植物，请重新拍摄一张清晰的植物照片。"}

重要规则：
- 必须使用扁平结构，禁止将字段放在 "personality" 或 "plant_identification" 等嵌套对象中。
- name要有创意，不能只是植物学名，要加上性格特征前缀
- tags必须恰好3个，每个2-6个字
- signature要有趣味性，像社交媒体个性签名
- iconKey和tone必须从列表中选择，不能自造
- 只输出JSON，不要有任何其他内容''';

  static const String _userPrompt = '''请仔细看这张植物照片，识别其中的植物，并为它赋予一个有趣的灵魂人格。记住只用JSON格式回复。''';

  String _buildSystemPrompt() {
    final iconKeys = PlantCatalog.availableIconKeys
        .map((k) => '- $k')
        .join('\n');
    return _systemPrompt.replaceAll('{ICON_KEYS}', iconKeys);
  }

  Future<RecognitionResult> recognizePlant(
    String imagePath,
    AppConfig config,
  ) async {
    final systemPrompt = _buildSystemPrompt();

    try {
      final rawResponse = await _callModel(
        systemPrompt: systemPrompt,
        userPrompt: _userPrompt,
        imagePath: imagePath,
        config: config,
      );

      return _parseResponse(rawResponse);
    } catch (e) {
      return RecognitionResult.failure(
        errorMessage: '调用模型异常: $e',
        errorType: 'model_call_error',
      );
    }
  }

  Future<String> _callModel({
    required String systemPrompt,
    required String userPrompt,
    required String imagePath,
    required AppConfig config,
  }) async {
    if (config.localModelPath.trim().isNotEmpty) {
      return _callLocalModel(
        systemPrompt: systemPrompt,
        userPrompt: userPrompt,
        imagePath: imagePath,
        config: config,
      );
    }

    if (config.apiUrl.trim().isNotEmpty) {
      return _callApiModel(
        systemPrompt: systemPrompt,
        userPrompt: userPrompt,
        imagePath: imagePath,
        config: config,
      );
    }

    throw Exception('未配置任何模型（本地模型路径和API地址均为空）');
  }

  Future<String> _callLocalModel({
    required String systemPrompt,
    required String userPrompt,
    required String imagePath,
    required AppConfig config,
  }) async {
    debugPrint('[CAMERA] ===== 开始识别 =====');
    debugPrint('[CAMERA] 模型路径: ${config.localModelPath}');
    debugPrint('[CAMERA] mmproj路径: ${config.localMmprojPath}');
    debugPrint('[CAMERA] contextSize: ${config.contextSize}');
    debugPrint('[CAMERA] imagePath: $imagePath');

    try {
      final imgFile = File(imagePath);
      final imgExists = await imgFile.exists();
      final imgSize = imgExists ? await imgFile.length() : 0;
      debugPrint('[CAMERA] 图片存在: $imgExists, 大小: $imgSize bytes');
    } catch (e) {
      debugPrint('[CAMERA] 检查图片失败: $e');
    }

    final result = await LocalModelCoordinator.runBackgroundTaskOrSkip(() async {
      await _ensureLocalModelReady(config);
      debugPrint('[CAMERA] 模型准备就绪，开始推理...');

      final buffer = StringBuffer();
      await for (final chunk in _localLlamaService.generateMultimodalResponse(
        systemPrompt,
        userPrompt,
        imagePath,
        maxTokens: 1024,
        forceDisableThinking: true,
        skipImage: false,
      )) {
        buffer.write(chunk);
      }

      return buffer.toString();
    });
    if (result == null) {
      throw Exception('聊天任务占用本地模型，请稍后再试识别');
    }
    debugPrint('[CAMERA] ===== 推理完成 =====');
    debugPrint('[CAMERA] 总长度: ${result.length}');
    debugPrint('[CAMERA] 完整输出: "$result"');

    return result;
  }

  Future<String> _callApiModel({
    required String systemPrompt,
    required String userPrompt,
    required String imagePath,
    required AppConfig config,
  }) async {
    throw Exception(
      'API模式暂不支持图片识别，请在配置中设置本地模型路径（需要支持视觉的模型，如LLaVA）。',
    );
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

  RecognitionResult _parseResponse(String rawResponse) {
    final cleaned = _cleanResponse(rawResponse);

    Map<String, dynamic> json;
    try {
      json = jsonDecode(cleaned) as Map<String, dynamic>;
    } catch (e) {
      final extracted = _tryExtractJson(cleaned);
      if (extracted != null) {
        try {
          json = jsonDecode(extracted) as Map<String, dynamic>;
        } catch (e2) {
          return RecognitionResult.failure(
            errorMessage: 'JSON解析失败: $e2',
            errorType: 'json_parse_error',
            rawResponse: rawResponse,
          );
        }
      } else {
        return RecognitionResult.failure(
          errorMessage: '模型输出不是有效的JSON格式: $e',
          errorType: 'json_parse_error',
          rawResponse: rawResponse,
        );
      }
    }

    if (json.containsKey('error')) {
      return RecognitionResult.failure(
        errorMessage: json['error'] as String,
        errorType: 'recognition_failed',
        rawResponse: rawResponse,
      );
    }

    return _buildProfileFromJson(json, rawResponse);
  }

  String _cleanResponse(String raw) {
    var cleaned = raw
        .replaceAll(RegExp(r'\[思考:[\s\S]*?\]'), '')
        .trim();

    // 处理各种可能的 Markdown 代码块定界符，包括中英文引号
    cleaned = cleaned
        .replaceAll(RegExp(r'^[`\x27"‘“]{3,}(json)?\s*', multiLine: true, caseSensitive: false), '')
        .replaceAll(RegExp(r'\s*[`\x27"’ ”]{3,}$', multiLine: true), '')
        .trim();

    // 如果清理后仍然不是以 { 开头，尝试强制提取第一个 { 和最后一个 } 之间的内容
    if (!cleaned.startsWith('{')) {
      final extracted = _tryExtractJson(cleaned);
      if (extracted != null) {
        cleaned = extracted;
      }
    }

    return cleaned;
  }

  String? _tryExtractJson(String text) {
    final braceMatch = RegExp(r'\{[\s\S]*\}').firstMatch(text);
    if (braceMatch != null) {
      return braceMatch.group(0);
    }
    return null;
  }

  RecognitionResult _buildProfileFromJson(
    Map<String, dynamic> json,
    String rawResponse,
  ) {
    // 尝试从嵌套对象中提取（处理如 "personality": { ... } 的情况）
    final Map<String, dynamic> data = _flattenJson(json);

    final name = _getString(data, ['name', 'plant_name']);
    if (name == null || name.trim().isEmpty) {
      return RecognitionResult.failure(
        errorMessage: '缺少必要字段: name',
        errorType: 'missing_field',
        rawResponse: rawResponse,
      );
    }

    // 尝试从各种可能的字段名中提取 tags
    List<String> tags = _getList(data, ['tags', 'traits', 'personality_traits', 'trait']);
    if (tags.isEmpty) {
      // 如果没有数组格式的标签，尝试从描述或昵称中构造
      final nickname = _getString(data, ['species_nickname', 'nickname']);
      if (nickname != null) tags.add(nickname);
      
      final trait = _getString(data, ['trait', 'personality']);
      if (trait != null) tags.add(trait);
      
      if (tags.isEmpty) {
        tags = ['神秘植物', '自然之子', '新朋友'];
      }
    }

    // 尝试提取 signature
    final signature = _getString(data, ['signature', 'description', 'bio', 'motto', 'intro']) ?? '你好！很高兴认识你。';

    final iconKey = _getString(data, ['iconKey', 'icon', 'avatar']) ?? 'leaf';
    final validIconKey = PlantCatalog.availableIconKeys.contains(iconKey)
        ? iconKey
        : 'leaf';

    final toneStr = _getString(data, ['tone', 'personality_type']) ?? 'warm';
    final tone = PlantTone.values.firstWhere(
      (t) => t.name == toneStr,
      orElse: () => PlantTone.warm,
    );

    final id = 'custom_${DateTime.now().millisecondsSinceEpoch}';

    final profile = PlantProfile(
      id: id,
      name: name.trim(),
      tags: tags.take(5).toList(),
      signature: signature.trim(),
      iconKey: validIconKey,
      tone: tone,
    );

    return RecognitionResult(
      profile: profile,
      isSuccess: true,
      rawResponse: rawResponse,
    );
  }

  // 辅助方法：递归展平所有嵌套 JSON 对象到根级别
  Map<String, dynamic> _flattenJson(Map<String, dynamic> json) {
    final Map<String, dynamic> result = {};
    _flattenRecursive(json, result);
    return result;
  }

  void _flattenRecursive(Map<String, dynamic> source, Map<String, dynamic> target) {
    for (final entry in source.entries) {
      if (entry.value is Map<String, dynamic>) {
        _flattenRecursive(entry.value as Map<String, dynamic>, target);
      } else {
        target.putIfAbsent(entry.key, () => entry.value);
      }
    }
  }

  String? _getString(Map<String, dynamic> data, List<String> keys) {
    for (final key in keys) {
      if (data[key] is String && (data[key] as String).isNotEmpty) {
        return data[key] as String;
      }
    }
    return null;
  }

  List<String> _getList(Map<String, dynamic> data, List<String> keys) {
    for (final key in keys) {
      if (data[key] is List) {
        return (data[key] as List).map((e) => e.toString()).toList();
      }
      if (data[key] is String) {
        // 如果是逗号分隔的字符串，尝试分割
        final str = data[key] as String;
        if (str.contains('，') || str.contains(',')) {
          return str.split(RegExp(r'[，,]')).map((e) => e.trim()).toList();
        }
      }
    }
    return [];
  }
}

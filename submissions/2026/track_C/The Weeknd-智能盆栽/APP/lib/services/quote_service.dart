import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:llamadart/llamadart.dart';
import '../models/app_config.dart';
import '../services/local_llama_service.dart';
import '../services/local_model_coordinator.dart';
import '../services/planter_service.dart';

class QuoteService {
  static final QuoteService _instance = QuoteService._internal();
  factory QuoteService() => _instance;
  QuoteService._internal();

  final LocalLlamaService _localLlamaService = LocalLlamaService();
  final PlanterService _planterService = PlanterService();
  String _currentLoadedModelPath = '';
  String _currentLoadedMmprojPath = '';
  bool _isGenerating = false;

  Future<String?> generateQuote({
    required AppConfig config,
    String memoryContext = '',
  }) async {
    if (_isGenerating) return null;
    _isGenerating = true;

    try {
      if (config.localModelPath.trim().isEmpty) {
        return null;
      }

      final quote = await LocalModelCoordinator.runBackgroundTaskOrSkip(() async {
        await _ensureLocalModelReady(config);

        final systemPrompt = 'You are a plant spirit who generates short, positive, motivational quotes in English. The quote must be 20 words or fewer. Output ONLY the quote text, nothing else. No quotation marks, no prefix, no explanation.';

        final userPrompt = memoryContext.isNotEmpty
            ? 'Based on this context, generate an uplifting quote:\n$memoryContext'
            : 'Generate a short uplifting quote for the start of a new day.';

        final messages = [
          LlamaChatMessage.fromText(role: LlamaChatRole.system, text: systemPrompt),
          LlamaChatMessage.fromText(role: LlamaChatRole.user, text: userPrompt),
        ];

        final buffer = StringBuffer();
        await for (final chunk in _localLlamaService.generateResponse(messages)) {
          buffer.write(chunk);
        }

        final raw = buffer.toString().trim();
        return _cleanQuote(raw);
      });
      return quote;
    } catch (e) {
      debugPrint('语录生成失败: $e');
      return null;
    } finally {
      _isGenerating = false;
    }
  }

  Future<bool> pushQuote(String quote, AppConfig config) async {
    return _planterService.sendQuote(config, quote);
  }

  Future<void> generateAndPush({
    required AppConfig config,
    String memoryContext = '',
  }) async {
    final quote = await generateQuote(
      config: config,
      memoryContext: memoryContext,
    );
    if (quote != null && quote.isNotEmpty) {
      await pushQuote(quote, config);
    }
  }

  String _cleanQuote(String raw) {
    var cleaned = raw
        .replaceAll(RegExp(r"""^['"']+"""), '')
        .replaceAll(RegExp(r"""['"']+$"""), '')
        .replaceAll(RegExp(r'^\s*Quote:\s*', caseSensitive: false), '')
        .trim();
    final words = cleaned.split(RegExp(r'\s+'));
    if (words.length > 20) {
      cleaned = words.take(20).join(' ');
    }
    return cleaned;
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
}

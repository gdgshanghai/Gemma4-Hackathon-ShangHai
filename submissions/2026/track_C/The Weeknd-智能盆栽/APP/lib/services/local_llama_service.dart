import 'dart:async';
import 'package:llamadart/llamadart.dart';

class LocalLlamaService {
  static final LocalLlamaService _instance = LocalLlamaService._internal();
  factory LocalLlamaService() => _instance;
  LocalLlamaService._internal();

  LlamaEngine? _engine;
  bool _isInitialized = false;
  bool _enableThinking = false;
  
  // 保存初始化参数，用于需要重新初始化时
  String? _modelPath;
  String? _mmprojPath;
  int? _threads;
  int _currentContextSize = 0;

  Future<void> init(String modelPath, String mmprojPath, int contextSize, int threads, bool enableThinking) async {
    if (_isInitialized) return;
    
    // 保存参数，用于可能的重新初始化
    _modelPath = modelPath;
    _mmprojPath = mmprojPath;
    _threads = threads;
    _currentContextSize = contextSize;
    
    try {
      final backend = LlamaBackend();
      _engine = LlamaEngine(backend);
      await _engine!.loadModel(
        modelPath,
        modelParams: ModelParams(
          contextSize: contextSize,
          numberOfThreads: threads,
          numberOfThreadsBatch: threads,
        ),
      );
      
      if (mmprojPath.trim().isNotEmpty) {
        await _engine!.loadMultimodalProjector(mmprojPath.trim());
      }
      
      _enableThinking = enableThinking;
      _isInitialized = true;
      print('[LocalLlama] 模型初始化成功，contextSize: $contextSize');
    } catch (e) {
      print('Failed to init local llama model: $e');
      throw Exception('本地模型加载失败: $e');
    }
  }
  
  /// 确保 context size 足够大多模态推理（最小 4096）
  Future<void> ensureMultimodalContextSize() async {
    if (!_isInitialized) return;
    
    // 如果当前 context size 已经 >= 4096，无需重新初始化
    if (_currentContextSize >= 4096) {
      print('[LocalLlama] Context size ${_currentContextSize} 已满足多模态需求');
      return;
    }
    
    // 需要重新初始化使用更大的 context size
    print('[LocalLlama] Context size ${_currentContextSize} 太小，重新初始化为 4096...');
    
    // 先销毁当前 engine
    await dispose();
    
    // 重新初始化，使用 4096 的 context size
    await init(_modelPath!, _mmprojPath!, 4096, _threads!, _enableThinking);
  }

  Stream<String> generateResponse(
    List<LlamaChatMessage> messages, {
    bool enforceContextLimit = true,
    int? maxNewTokens,
  }) async* {
    if (!_isInitialized || _engine == null) {
      throw Exception('本地模型未初始化');
    }

    try {
      final chatSession = ChatSession(_engine!);
      
      if (!enforceContextLimit) {
        chatSession.maxContextTokens = 0;
      }

      final generationParams = GenerationParams(
        maxTokens: maxNewTokens ?? 4096,
        reusePromptPrefix: false,
      );

      final userMessage = messages.last;

      for (var i = 0; i < messages.length - 1; i++) {
        final msg = messages[i];
        if (msg.role == LlamaChatRole.system) {
          chatSession.systemPrompt = msg.parts
              .whereType<LlamaTextContent>()
              .map((p) => p.text)
              .join('');
        } else {
          chatSession.addMessage(msg);
        }
      }

      await for (final chunk in chatSession.create(
        userMessage.parts,
        params: generationParams,
        enableThinking: _enableThinking,
      )) {
        final content = chunk.choices.first.delta.content;
        final thinking = chunk.choices.first.delta.thinking;

        if (thinking != null && thinking.isNotEmpty) {
          yield '[思考: $thinking]';
        }

        if (content != null && content.isNotEmpty) {
          yield content;
        }
      }
    } catch (e) {
      yield '\n[本地推理出错: $e]';
    }
  }

  Stream<String> generateMultimodalResponse(
    String systemPrompt,
    String userText,
    String imagePath, {
    int maxTokens = 1024,
    bool forceDisableThinking = false,
    bool skipImage = false,
  }) async* {
    if (!_isInitialized || _engine == null) {
      throw Exception('本地模型未初始化');
    }

    // 多模态推理需要更大的 context size（至少 4096）
    if (!skipImage && imagePath.isNotEmpty) {
      print('[LLM-VM] 多模态模式，检查 context size...');
      await ensureMultimodalContextSize();
    }

    final useThinking = forceDisableThinking ? false : _enableThinking;
    print('[LLM-VM] enableThinking(原始): $_enableThinking');
    print('[LLM-VM] enableThinking(实际): $useThinking');
    print('[LLM-VM] maxTokens: $maxTokens');
    print('[LLM-VM] skipImage: $skipImage');
    print('[LLM-VM] imagePath: $imagePath');

    try {
      final messages = <LlamaChatMessage>[
        LlamaChatMessage.fromText(
          role: LlamaChatRole.system,
          text: systemPrompt,
        ),
      ];

      if (skipImage || imagePath.isEmpty) {
        // 纯文字模式
        print('[LLM-VM] 纯文字模式，不传图片');
        messages.add(LlamaChatMessage.fromText(
          role: LlamaChatRole.user,
          text: userText,
        ));
      } else {
        // 多模态模式
        print('[LLM-VM] 多模态模式，传图片');
        messages.add(LlamaChatMessage.withContent(
          role: LlamaChatRole.user,
          content: [
            LlamaTextContent(userText),
            LlamaImageContent(path: imagePath),
          ],
        ));
      }

      final params = GenerationParams(maxTokens: maxTokens);

      int totalChunks = 0;
      int thinkingChunks = 0;
      int contentChunks = 0;

      await for (final chunk in _engine!.create(
        messages,
        params: params,
        enableThinking: useThinking,
      )) {
        totalChunks++;
        final content = chunk.choices.first.delta.content;
        final thinking = chunk.choices.first.delta.thinking;
        final finishReason = chunk.choices.first.finishReason;

        print('[LLM-VM] chunk #$totalChunks | content: "${content ?? "null"}" | thinking: "${thinking != null ? (thinking.length > 50 ? thinking.substring(0, 50) + '...' : thinking) : "null"}" | finishReason: $finishReason');

        if (thinking != null && thinking.isNotEmpty) {
          thinkingChunks++;
        }

        if (content != null && content.isNotEmpty) {
          contentChunks++;
          yield content;
        }

        if (finishReason != null && finishReason != '') {
          print('[LLM-VM] 生成结束! finishReason: $finishReason');
          break;
        }
      }

      print('[LLM-VM] 流结束 | 总chunks: $totalChunks | thinking: $thinkingChunks | content: $contentChunks');
    } catch (e, st) {
      print('[LLM-VM] 推理异常: $e');
      print('[LLM-VM] 堆栈: $st');
      yield '\n[多模态推理出错: $e]';
    }
  }

  Future<void> dispose() async {
    if (_engine != null) {
      await _engine!.dispose();
      _engine = null;
    }
    _isInitialized = false;
  }
}

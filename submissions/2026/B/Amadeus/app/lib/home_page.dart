import 'dart:convert';
import 'dart:async';
import 'dart:math' as math;
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:camera/camera.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:file_selector/file_selector.dart';
import 'package:http/http.dart' as http;
import 'package:image/image.dart' as img;
import 'package:image_picker/image_picker.dart' as image_picker;
import 'package:speech_to_text/speech_to_text.dart' as stt;

/// Data class to pass parameters to the background image processing task
class _ImageProcessParams {
  final Uint8List bytes;
  final int maxEdge;
  final int quality;
  _ImageProcessParams(this.bytes, this.maxEdge, this.quality);
}

/// Result class for background image processing
class _ImageProcessResult {
  final String base64;
  final String note;
  _ImageProcessResult(this.base64, this.note);
}

class _UiSkin {
  final String name;
  final bool isDark;
  final Color background;
  final Color surface;
  final Color elevatedSurface;
  final Color primary;
  final Color primarySoft;
  final Color accent;
  final Color text;
  final Color mutedText;
  final Color border;
  final Color glow;

  const _UiSkin({
    required this.name,
    required this.isDark,
    required this.background,
    required this.surface,
    required this.elevatedSurface,
    required this.primary,
    required this.primarySoft,
    required this.accent,
    required this.text,
    required this.mutedText,
    required this.border,
    required this.glow,
  });
}

const _lightSkin = _UiSkin(
  name: 'light',
  isDark: false,
  background: Color(0xFFF7F0E3),
  surface: Color(0xFFFFFBF1),
  elevatedSurface: Color(0xFFF0E7D7),
  primary: Color(0xFF2F4F46), // 深松绿色
  primarySoft: Color(0xFFA7C5B7),
  accent: Color(0xFFD4AF37),
  text: Color(0xFF243A34),
  mutedText: Color(0xFF746A5D),
  border: Color(0xFFD8C9AD),
  glow: Color(0x55D4AF37),
);

const _darkSkin = _UiSkin(
  name: 'dark',
  isDark: true,
  background: Color(0xFF061012),
  surface: Color(0xFF0B1F22),
  elevatedSurface: Color(0xFF102B2F),
  primary: Color(0xFF22E6F0),
  primarySoft: Color(0xFF0E5C5B),
  accent: Color(0xFFFFB45A),
  text: Color(0xFFE6FBF8),
  mutedText: Color(0xFF8FC3BE),
  border: Color(0xFF1C6C70),
  glow: Color(0x6622E6F0),
);

const _cuteSkin = _UiSkin(
  name: 'cute',
  isDark: false,
  background: Color(0xFFFFF5F5), // 淡淡的樱花粉
  surface: Color(0xFFFFFFFF),
  elevatedSurface: Color(0xFFFFE8E8),
  primary: Color(0xFFFF8B8B), // 暖粉色
  primarySoft: Color(0xFFFFCACA),
  accent: Color(0xFFFFD93D), // 明亮黄
  text: Color(0xFF6B4D4D),
  mutedText: Color(0xFFA08585),
  border: Color(0xFFFFD1D1),
  glow: Color(0x33FF8B8B),
);

/// Top-level function for background image processing to avoid blocking the UI thread
/// This addresses the "Reported frame time is older than the last one" jitter.
_ImageProcessResult _processImageTask(_ImageProcessParams params) {
  final decoded = img.decodeImage(params.bytes);
  if (decoded == null) {
    return _ImageProcessResult(base64Encode(params.bytes), "图片预处理跳过（无法解码）");
  }

  final width = decoded.width;
  final height = decoded.height;
  final longest = width > height ? width : height;

  img.Image processed = decoded;
  String note = "原图 ${width}x$height";

  if (params.maxEdge > 0 && longest > params.maxEdge) {
    final scale = params.maxEdge / longest;
    final newW = (width * scale).round();
    final newH = (height * scale).round();
    processed = img.copyResize(
      decoded,
      width: newW,
      height: newH,
      interpolation: img.Interpolation.linear,
    );
    note += " → 缩放 ${newW}x$newH";
  }

  final q = params.quality.clamp(1, 100);
  final jpegBytes = img.encodeJpg(processed, quality: q);
  note += "，JPEG Q=$q";

  return _ImageProcessResult(base64Encode(jpegBytes), note);
}

/// 翻译字典
const _translations = {
  'zh': {
    'status_initial': '请拍摄一件陶瓷以获取讲解。',
    'status_captured': '已拍摄图片，点击“开始识别”即可分析。',
    'status_selected': '已选择图片，立刻分析吧。',
    'status_no_camera': '当前设备没有可用摄像头，请使用“选择照片识别”。',
    'status_need_image': '请先拍摄或选择一张图片。',
    'take_photo': '拍摄',
    'select_image': '选择图片',
    'start_id': '开始识别（本地模型）',
    'label_selected': '已选器物',
    'label_live': '实时取景',
    'hint_select': '请选择或拍摄陶瓷器物图片',
    'report_title': '报告',
    'name': '名称',
    'characteristics': '特点',
    'guide_says': '小瓷为您解读:',
    'analyzing': '小瓷正在翻阅考古秘籍...',
    'voice_followup': '语音追问',
    'listening': '正在倾听...',
    'start_asking': '开始提问',
    'end_send': '结束并发送',
    'voice_hint': '点击按钮向我提问吧',
    'wait': '正在识别图片并分析中，请稍候...',
    'prompt_system':
        "你是一位极富感染力的博物馆金牌陶瓷讲解员。请识别图片中的陶瓷器物，并只用 JSON 返回结构化结果。\nJSON 必须包含字段：\n- name: 名称\n- characteristics: 纹饰与工艺特点\n- history: 一段生动优美的导览讲解稿（100字）\n要求：语言亲切自然，核心内容重点描述器物的釉色之美、造型意趣及文化底蕴。",
    'prompt_retry': "只输出一个包含 name/characteristics/history 字段的中文 JSON 对象。不要解释。",
  },
  'en': {
    'status_initial': 'Take a photo of a ceramic for explanation.',
    'status_captured': 'Photo captured. Tap "Start ID" to analyze.',
    'status_selected': 'Image selected. Start analysis now.',
    'status_no_camera': 'No camera available. Please select a photo.',
    'status_need_image': 'Please capture or select an image first.',
    'take_photo': 'Capture',
    'select_image': 'Library',
    'start_id': 'Start Identification (Local)',
    'label_selected': 'Selected',
    'label_live': 'Live View',
    'hint_select': 'Select or capture a ceramic image',
    'report_title': 'Report',
    'name': 'Name',
    'characteristics': 'Traits',
    'guide_says': 'Xiao Ci Explains:',
    'analyzing': 'Xiao Ci is checking records...',
    'voice_followup': 'Voice Follow-up',
    'listening': 'Listening...',
    'start_asking': 'Ask Me',
    'end_send': 'Send',
    'voice_hint': 'Tap to ask me a question',
    'wait': 'Identifying and analyzing image, please wait...',
    'prompt_system':
        "You are a world-class ceramic museum guide. Identify the ceramic in the image and return ONLY a JSON object.\nFields:\n- name: Name\n- characteristics: Craft traits\n- history: A vivid, beautiful guide script (100 words)\nRequirements: Language must be warm and professional. Focus on glaze beauty, form, and cultural heritage. Output in English.",
    'prompt_retry':
        "Output ONLY an English JSON object with name/characteristics/history fields. No explanations.",
  },
};

/// 获取翻译的便捷函数
String _t(String key, bool useEnglish) {
  final lang = useEnglish ? 'en' : 'zh';
  return _translations[lang]?[key] ?? key;
}

/// 结果展示与语音追问子页面
class ResultPage extends StatefulWidget {
  final Uint8List imageBytes;
  final String ollamaBaseUrl;
  final String ollamaModel;
  final bool useDarkSkin;
  final bool useEnglish;
  final int numCtx;
  final int numPredict;
  final double temperature;
  final int maxImageEdge;
  final int jpegQuality;

  const ResultPage({
    super.key,
    required this.imageBytes,
    required this.ollamaBaseUrl,
    required this.ollamaModel,
    required this.useDarkSkin,
    required this.useEnglish,
    required this.numCtx,
    required this.numPredict,
    required this.temperature,
    required this.maxImageEdge,
    required this.jpegQuality,
  });

  @override
  State<ResultPage> createState() => _ResultPageState();
}

class _ResultPageState extends State<ResultPage> with TickerProviderStateMixin {
  final FlutterTts _flutterTts = FlutterTts();
  final stt.SpeechToText _speechToText = stt.SpeechToText();

  late AnimationController _skeletonController;
  late Animation<double> _skeletonAnimation;

  late AnimationController _mascotController;
  late Animation<double> _mascotFloatAnimation;

  late AnimationController _successController;
  late Animation<double> _successAnimation;

  late AnimationController _thinkingController;
  late Animation<double> _thinkingAnimation;

  late AnimationController _cornerController;
  late Animation<double> _cornerAnimation;

  late AnimationController _voiceHaloController;

  bool _isAnalyzing = true;
  late String _analysisResult;
  String _displayedAnalysisResult = "";
  Timer? _typewriterTimer;
  Map<String, dynamic>? _structuredData;
  bool _isSpeechInitialized = false;
  bool _speechAvailable = false;
  bool _isListening = false;
  String _recognizedSpeechText = '';
  String _lastAnsweredQuestion = '';

  _UiSkin get _skin => widget.useDarkSkin ? _darkSkin : _lightSkin;

  @override
  void initState() {
    super.initState();
    _skeletonController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat(reverse: true);
    _skeletonAnimation = Tween<double>(
      begin: 0.4,
      end: 1.0,
    ).animate(_skeletonController);

    // 小瓷悬浮动画：2秒为一个周期，平滑上下浮动
    _mascotController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _mascotFloatAnimation =
        Tween<double>(
          begin: 0.0,
          end: 8.0, // 向上浮动 8 像素
        ).animate(
          CurvedAnimation(
            parent: _mascotController,
            curve: Curves.easeInOutSine,
          ),
        );

    // “识别成功”的开心动画：1.2秒的跳跃+旋转
    _successController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );
    _successAnimation = CurvedAnimation(
      parent: _successController,
      curve: Curves.easeOutBack,
    );

    // “思考中”的点头/摇摆动画：500毫秒一个周期
    _thinkingController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );
    _thinkingAnimation = Tween<double>(begin: -0.08, end: 0.08).animate(
      CurvedAnimation(parent: _thinkingController, curve: Curves.easeInOutSine),
    );

    _cornerController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _cornerAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(_cornerController);

    _voiceHaloController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );

    _analysisResult = _t('wait', widget.useEnglish);
    _displayedAnalysisResult = _analysisResult;
    _initializeTts();
    _analyzeImage();
  }

  @override
  void dispose() {
    _flutterTts.stop();
    _speechToText.stop();
    _skeletonController.dispose();
    _mascotController.dispose();
    _successController.dispose();
    _thinkingController.dispose();
    _cornerController.dispose();
    _voiceHaloController.dispose();
    _typewriterTimer?.cancel();
    super.dispose();
  }

  void _startTypewriterEffect(String text) {
    _typewriterTimer?.cancel();
    _displayedAnalysisResult = "";
    int index = 0;
    // 20ms 的间隔，产生流畅的打字感
    _typewriterTimer = Timer.periodic(const Duration(milliseconds: 20), (
      timer,
    ) {
      if (index < text.length) {
        if (mounted) {
          setState(() {
            _displayedAnalysisResult += text[index];
          });
        }
        index++;
      } else {
        timer.cancel();
      }
    });
  }

  Future<void> _initializeTts() async {
    // 1. 设置语言（必须 await 确保设置成功）
    String lang = widget.useEnglish ? "en-US" : "zh-CN";
    await _flutterTts.setLanguage(lang);

    // 2. iOS 专用设置：确保在静音模式下也能发声，并使用播放类别
    if (Platform.isIOS) {
      await _flutterTts
          .setIosAudioCategory(IosTextToSpeechAudioCategory.playback, [
            IosTextToSpeechAudioCategoryOptions.allowBluetooth,
            IosTextToSpeechAudioCategoryOptions.allowBluetoothA2DP,
          ]);
    }

    // 3. 设置语速和音调
    await _flutterTts.setSpeechRate(0.55);
    await _flutterTts.setPitch(1.0);
  }

  Future<void> _analyzeImage() async {
    try {
      final base64Image = await compute(
        _processImageTask,
        _ImageProcessParams(
          widget.imageBytes,
          widget.maxImageEdge,
          widget.jpegQuality,
        ),
      ).then((res) => res.base64);

      final prompt = _t('prompt_system', widget.useEnglish);

      final decoded = await _ollamaChat(
        prompt: prompt,
        base64Image: base64Image,
      );

      String modelText = _extractFirstJsonObject(_contentFrom(decoded));

      if (!modelText.trim().startsWith('{')) {
        // 重试逻辑
        final retryDecoded = await _ollamaChat(
          prompt: _t('prompt_retry', widget.useEnglish),
          base64Image: base64Image,
          overrideNumPredict: 1024,
        );
        modelText = _extractFirstJsonObject(_contentFrom(retryDecoded));
      }

      final Map<String, dynamic> data =
          jsonDecode(modelText) as Map<String, dynamic>;

      if (!mounted) return;
      setState(() {
        _structuredData = data;
        _analysisResult =
            data['history'] ??
            (widget.useEnglish ? "No history available." : "未获取到历史背景。");
        _isAnalyzing = false;
      });

      _startTypewriterEffect(_analysisResult);
      _cornerController.repeat(reverse: true); // 识别成功，开始闪烁金光
      _successController.forward(from: 0.0); // 新增：播放开心动画
      await _speakResult(_analysisResult);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _analysisResult = "分析失败: $e";
        _displayedAnalysisResult = _analysisResult;
        _isAnalyzing = false;
      });
    }
  }

  String _contentFrom(Map<String, dynamic> decoded) {
    final message = decoded["message"];
    if (message is! Map<String, dynamic>) return "";
    return message["content"]?.toString() ??
        message["thinking"]?.toString() ??
        "";
  }

  String _extractFirstJsonObject(String text) {
    final start = text.indexOf('{');
    final end = text.lastIndexOf('}');
    if (start == -1 || end == -1) return text;
    return text.substring(start, end + 1);
  }

  Future<Map<String, dynamic>> _ollamaChat({
    required String prompt,
    required String base64Image,
    int? overrideNumPredict,
  }) async {
    final uri = Uri.parse("${widget.ollamaBaseUrl}/api/chat");
    final payload = {
      "model": widget.ollamaModel,
      "stream": false,
      "options": {
        "num_ctx": widget.numCtx,
        "num_predict": overrideNumPredict ?? widget.numPredict,
        "temperature": widget.temperature,
      },
      "messages": [
        {
          "role": "system",
          "content": widget.useEnglish
              ? "You are a JSON assistant."
              : "你是一个只输出 JSON 的助手。",
        },
        {
          "role": "user",
          "content": prompt,
          "images": [base64Image],
        },
      ],
    };

    final resp = await http
        .post(
          uri,
          headers: {"Content-Type": "application/json"},
          body: jsonEncode(payload),
        )
        .timeout(const Duration(minutes: 5));

    return jsonDecode(resp.body);
  }

  Future<void> _speakResult(String text) async {
    await _flutterTts.stop();
    await _flutterTts.speak(text);
  }

  Future<void> _initializeSpeech() async {
    if (_isSpeechInitialized) return;
    final available = await _speechToText.initialize();
    setState(() {
      _speechAvailable = available;
      _isSpeechInitialized = true;
    });
  }

  Future<void> _startRecording() async {
    await _initializeSpeech();
    if (!_speechAvailable) return;
    setState(() {
      _isListening = true;
      _recognizedSpeechText = '';
    });
    _voiceHaloController.repeat(reverse: true); // 开始呼吸灯动画
    await _speechToText.listen(
      localeId: widget.useEnglish ? "en-US" : "zh-CN",
      listenMode: stt.ListenMode.dictation,
      partialResults: true,
      cancelOnError: false,
      onResult: (result) {
        setState(() => _recognizedSpeechText = result.recognizedWords);
        if (result.finalResult) _stopRecording();
      },
    );
  }

  Future<void> _stopRecording() async {
    await _speechToText.stop();
    _voiceHaloController.stop();
    _voiceHaloController.reset(); // 停止并重置呼吸灯动画
    setState(() => _isListening = false);
    if (_recognizedSpeechText.isNotEmpty) {
      _answerQuestion(_recognizedSpeechText);
    }
  }

  Future<void> _answerQuestion(String question) async {
    if (question == _lastAnsweredQuestion) return;
    setState(() {
      _isAnalyzing = true;
      _lastAnsweredQuestion = question;
      _analysisResult = widget.useEnglish ? "Thinking..." : "正在思索中...";
      _displayedAnalysisResult = _analysisResult;
      _thinkingController.repeat(reverse: true); // 开始“思考”动画
    });

    try {
      final uri = Uri.parse("${widget.ollamaBaseUrl}/api/chat");
      final systemPrompt = widget.useEnglish
          ? "You are Xiao Ci, a cute ceramic museum guide. Answer the visitor in English. Stay friendly and professional. No JSON."
          : "你是小瓷，陶瓷博物馆的可爱讲解员。请用中文回答游客，语气要亲切、专业。不要输出 JSON 或 Markdown。";
      final payload = {
        "model": widget.ollamaModel,
        "stream": false,
        "messages": [
          {"role": "system", "content": systemPrompt},
          {
            "role": "user",
            "content": widget.useEnglish
                ? "Known artifact info: ${jsonEncode(_structuredData)}\nVisitor asks: $question\nAnswer in 50-100 words."
                : "已知文物信息：${jsonEncode(_structuredData)}\n游客问：$question\n请在50-100字内回答。",
          },
        ],
      };
      final resp = await http.post(
        uri,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode(payload),
      );
      final answer = jsonDecode(resp.body)["message"]["content"];
      setState(() {
        _analysisResult = answer.trim();
        _displayedAnalysisResult = _analysisResult;
        _isAnalyzing = false;
        _thinkingController.stop(); // 停止动画
        _thinkingController.animateTo(0.0); // 回归原位
      });
      _startTypewriterEffect(answer);
      _speakResult(answer);
    } catch (e) {
      setState(() {
        _analysisResult = "追问失败: $e";
        _displayedAnalysisResult = _analysisResult;
        _isAnalyzing = false;
        _thinkingController.stop();
        _thinkingController.animateTo(0.0);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final skin = _skin;
    // 根据屏幕高度动态计算图片高度，比例设为屏幕高度的 40%，限制在 200 到 500 之间防止变形
    final screenHeight = MediaQuery.of(context).size.height;
    final imageHeight = (screenHeight * 0.4).clamp(200.0, 500.0);

    return Scaffold(
      backgroundColor: skin.background,
      body: CustomScrollView(
        physics: const BouncingScrollPhysics(),
        slivers: [
          SliverAppBar(
            expandedHeight: imageHeight,
            pinned: true,
            stretch: true,
            backgroundColor: skin.background,
            leading: BackButton(color: skin.text),
            flexibleSpace: FlexibleSpaceBar(
              stretchModes: const [StretchMode.zoomBackground],
              background: Hero(
                tag: 'artifact_image',
                child: Image.memory(widget.imageBytes, fit: BoxFit.cover),
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 100),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildReportHeader(skin),
                  const SizedBox(height: 24),
                  Container(
                    decoration: BoxDecoration(
                      color: skin.surface,
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: skin.border),
                      boxShadow: [
                        BoxShadow(
                          color: skin.primary.withOpacity(0.1),
                          blurRadius: 20,
                          offset: const Offset(0, 10),
                        ),
                        BoxShadow(
                          color: Colors.white.withOpacity(0.5),
                          blurRadius: 0,
                          offset: const Offset(-2, -2),
                        ),
                      ],
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (_structuredData != null) ...[
                            _buildInfoRow(
                              _t('name', widget.useEnglish),
                              _structuredData!['name'],
                              skin,
                            ),
                            _buildInfoRow(
                              _t('characteristics', widget.useEnglish),
                              _structuredData!['characteristics'],
                              skin,
                            ),
                            const Divider(),
                          ],
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // 使用 Listenable.merge 合并多个动画，提高性能并简化代码结构
                              AnimatedBuilder(
                                animation: Listenable.merge([
                                  _mascotFloatAnimation,
                                  _skeletonAnimation,
                                  _successAnimation, // 合并开心动画
                                  _thinkingAnimation, // 合并思考动画
                                ]),
                                builder: (context, _) {
                                  return Transform.translate(
                                    offset: Offset(
                                      0,
                                      // 基础悬浮 Y 轴偏移 + 成功时的跳跃 Y 轴偏移
                                      -_mascotFloatAnimation.value -
                                          (30 *
                                              math.sin(
                                                _successAnimation.value *
                                                    math.pi,
                                              )),
                                    ),
                                    child: Transform.rotate(
                                      // 组合旋转：成功时的360度旋转 + 思考时的轻微摇摆
                                      angle:
                                          (_successAnimation.value *
                                              2 *
                                              math.pi) +
                                          (_isAnalyzing
                                              ? _thinkingAnimation.value
                                              : 0.0),
                                      child: Opacity(
                                        // 分析时呈现呼吸脉冲效果
                                        opacity: _isAnalyzing
                                            ? _skeletonAnimation.value
                                            : 1.0,
                                        child: Image.asset(
                                          'assets/mascot_xiaoci.png',
                                          width: 64,
                                          height: 64,
                                          fit: BoxFit.contain,
                                        ),
                                      ),
                                    ),
                                  );
                                },
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      _isAnalyzing
                                          ? _t('analyzing', widget.useEnglish)
                                          : _t('guide_says', widget.useEnglish),
                                      style: TextStyle(
                                        fontWeight: FontWeight.bold,
                                        color: skin.primary,
                                        fontSize: 16,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    // 气泡样式的文字区域
                                    Container(
                                      padding: const EdgeInsets.all(12),
                                      decoration: BoxDecoration(
                                        color: skin.elevatedSurface,
                                        borderRadius: const BorderRadius.only(
                                          topRight: Radius.circular(16),
                                          bottomLeft: Radius.circular(16),
                                          bottomRight: Radius.circular(16),
                                        ),
                                      ),
                                      child: Text(
                                        _displayedAnalysisResult,
                                        style: TextStyle(
                                          fontSize: 15,
                                          height: 1.5,
                                          color: skin.text,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          Align(
                            alignment: Alignment.bottomRight,
                            child: IconButton(
                              icon: Icon(Icons.volume_up, color: skin.accent),
                              onPressed: _isAnalyzing
                                  ? null
                                  : () => _speakResult(_analysisResult),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  _buildVoiceSection(skin),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReportHeader(_UiSkin skin) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          _t('report_title', widget.useEnglish),
          style: TextStyle(
            color: skin.text,
            fontSize: 28,
            fontWeight: FontWeight.bold,
            letterSpacing: 2,
          ),
        ),
        Container(
          margin: const EdgeInsets.only(top: 8),
          height: 3,
          width: 60,
          color: skin.accent,
        ),
      ],
    );
  }

  Widget _buildVoiceSection(_UiSkin skin) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: skin.elevatedSurface,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: skin.border),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Icon(Icons.mic, color: _isListening ? Colors.red : skin.text),
              const SizedBox(width: 8),
              Text(
                _isListening
                    ? _t('listening', widget.useEnglish)
                    : _t('voice_followup', widget.useEnglish),
                style: TextStyle(fontWeight: FontWeight.bold, color: skin.text),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            _recognizedSpeechText.isEmpty
                ? _t('voice_hint', widget.useEnglish)
                : _recognizedSpeechText,
            style: TextStyle(color: skin.mutedText, fontSize: 14),
          ),
          const SizedBox(height: 15),
          Row(
            children: [
              Expanded(
                child: AnimatedBuilder(
                  animation: _voiceHaloController,
                  builder: (context, child) {
                    return Container(
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: _isListening
                            ? [
                                BoxShadow(
                                  color: skin.accent.withOpacity(
                                    0.6 * (1 - _voiceHaloController.value),
                                  ),
                                  blurRadius: 20 * _voiceHaloController.value,
                                  spreadRadius: 4 * _voiceHaloController.value,
                                ),
                              ]
                            : null,
                      ),
                      child: child,
                    );
                  },
                  child: ElevatedButton(
                    onPressed: _isAnalyzing || _isListening
                        ? null
                        : _startRecording,
                    style: _primaryButtonStyle(skin, height: 44),
                    child: Text(_t('start_asking', widget.useEnglish)),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton(
                  onPressed: _isListening ? _stopRecording : null,
                  style: OutlinedButton.styleFrom(
                    side: BorderSide(color: skin.primary),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: Text(_t('end_send', widget.useEnglish)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  ButtonStyle _primaryButtonStyle(_UiSkin skin, {double height = 48}) {
    return ButtonStyle(
      minimumSize: WidgetStateProperty.all(Size.fromHeight(height)),
      backgroundColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.pressed))
          return skin.primary.withOpacity(0.8);
        return skin.primary;
      }),
      foregroundColor: WidgetStateProperty.all(
        skin.background,
      ), // 使用背景色作为文字色，即近白色
      elevation: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.pressed)) return 2;
        return 8; // 默认较高，产生立体厚重感
      }),
      side: WidgetStateProperty.all(
        BorderSide(color: skin.accent, width: 1.5),
      ), // 金色勾边
      shape: WidgetStateProperty.all(
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      shadowColor: WidgetStateProperty.all(skin.primary.withOpacity(0.5)),
    ).copyWith(overlayColor: WidgetStateProperty.all(Colors.white10));
  }

  Widget _buildInfoRow(String label, dynamic value, _UiSkin skin) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Text.rich(
        TextSpan(
          children: [
            TextSpan(
              text: "$label: ",
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: skin.primary,
              ),
            ),
            TextSpan(
              text: "${value ?? (widget.useEnglish ? 'Unknown' : '未知')}",
              style: TextStyle(color: skin.text),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSkeletonItem({
    required double width,
    required double height,
    required _UiSkin skin,
  }) {
    return FadeTransition(
      opacity: _skeletonAnimation,
      child: Container(
        width: width,
        height: height,
        margin: const EdgeInsets.symmetric(vertical: 4),
        decoration: BoxDecoration(
          color: skin.primary.withOpacity(0.1),
          borderRadius: BorderRadius.circular(6),
        ),
      ),
    );
  }
}

class HomePage extends StatefulWidget {
  final CameraDescription? camera;

  const HomePage({super.key, required this.camera});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String _ollamaBaseUrl = const String.fromEnvironment(
    'OLLAMA_BASE_URL',
    defaultValue: 'http://localhost:11434',
  );
  String _ollamaModel = const String.fromEnvironment(
    'OLLAMA_MODEL',
    defaultValue: 'gemma4:e2b',
  );

  CameraController? _cameraController;
  Future<void>? _initializeControllerFuture;
  final image_picker.ImagePicker _imagePicker = image_picker.ImagePicker();

  String _homeStatusKey = 'status_initial';
  bool _isAnalyzing = false;
  Uint8List? _selectedImageBytes;
  bool _useDarkSkin = false;
  bool _useEnglish = false;

  int _numCtx = const int.fromEnvironment('OLLAMA_NUM_CTX', defaultValue: 2048);
  int _numPredict = const int.fromEnvironment(
    'OLLAMA_NUM_PREDICT',
    defaultValue: 450,
  );
  double _temperature =
      double.tryParse(
        const String.fromEnvironment('OLLAMA_TEMPERATURE', defaultValue: '0.2'),
      ) ??
      0.2;
  int _maxImageEdge = const int.fromEnvironment(
    'IMAGE_MAX_EDGE',
    defaultValue: 768,
  );
  int _jpegQuality = const int.fromEnvironment(
    'IMAGE_JPEG_QUALITY',
    defaultValue: 40,
  );
  static const double _ttsSpeechRate = 0.80;

  _UiSkin get _skin => _useDarkSkin ? _darkSkin : _lightSkin;

  String get _homeStatusText => _t(_homeStatusKey, _useEnglish);

  /// 从外部配置文件加载配置
  Future<void> _loadExternalConfig() async {
    try {
      // Ensure config.json is in your assets in pubspec.yaml
      final content = await rootBundle
          .loadString('config.json')
          .catchError((_) => "");
      if (content.isEmpty) {
        print("外部配置文件为空或不存在");
        return;
      }
      final config = jsonDecode(content);
      setState(() {
        if (config['OLLAMA_BASE_URL'] != null) {
          _ollamaBaseUrl = config['OLLAMA_BASE_URL'].toString();
        }
        if (config['OLLAMA_MODEL'] != null) {
          _ollamaModel = config['OLLAMA_MODEL'].toString();
        }
      });
      debugPrint("✅ 已加载配置: URL=$_ollamaBaseUrl, Model=$_ollamaModel");
    } catch (e) {
      debugPrint("❌ 加载外部配置失败: $e");
    }
  }

  /// 触发 iOS 本地网络权限弹窗的“预热”请求
  Future<void> _triggerLocalNetworkPrompt() async {
    if (!Platform.isIOS) return;

    try {
      // 解析基础 URL 的 Host
      final host = Uri.parse(_ollamaBaseUrl).host;
      if (host.isEmpty || host == 'localhost') return;

      debugPrint("📡 发起预热请求以触发本地网络权限...");
      // 尝试建立一个极短超时的 Socket 连接，仅为了触发系统权限检测
      final socket = await Socket.connect(
        host,
        11434,
        timeout: const Duration(seconds: 2),
      );
      await socket.close();
    } catch (_) {
      // 预热请求通常会失败（因为没传数据），我们只需要它触发系统弹窗即可
    }
  }

  @override
  void initState() {
    super.initState();

    _initializeCamera();
    _loadExternalConfig().then((_) {
      // 配置加载完成后，立即触发权限弹窗，避免调试器超时
      _triggerLocalNetworkPrompt();
    });
  }

  void _initializeCamera() {
    if (widget.camera == null) return;

    _cameraController = CameraController(
      widget.camera!,
      ResolutionPreset.high,
      enableAudio: false, // 考古助手不需要录音
    );

    _initializeControllerFuture = _cameraController!.initialize();
  }

  Future<void> _takePicture() async {
    if (_isAnalyzing) return;
    if (_cameraController == null || _initializeControllerFuture == null) {
      setState(() {
        _homeStatusKey = 'status_no_camera';
      });
      return;
    }

    try {
      setState(() {
        _homeStatusKey = 'status_captured';
        _selectedImageBytes = null;
      });

      await _initializeControllerFuture; // 确保相机控制器已初始化

      HapticFeedback.mediumImpact(); // 模拟快门触感
      final XFile image = await _cameraController!.takePicture();
      await _selectImageFile(image, "已拍摄图片，点击“开始识别”即可分析。");
    } catch (e) {
      print(e);
    }
  }

  Future<void> _pickImageAndAnalyze() async {
    if (_isAnalyzing) return;

    try {
      final XFile? picked;
      if (Platform.isIOS || Platform.isAndroid) {
        picked = await _imagePicker.pickImage(
          source: image_picker.ImageSource.gallery,
          requestFullMetadata: false,
        );
      } else {
        picked = await openFile(
          acceptedTypeGroups: [
            XTypeGroup(
              label: 'images',
              extensions: const ['jpg', 'jpeg', 'png', 'webp', 'heic', 'heif'],
            ),
          ],
        );
      }

      if (picked == null) return;

      await _selectImageFile(picked, 'status_selected');
    } catch (e) {
      debugPrint('选择图片失败: $e');
      setState(() {
        _homeStatusKey = 'status_initial';
      });
    }
  }

  bool _isSupportedImageName(String name) {
    final ext = name.toLowerCase().split('.').last;
    return switch (ext) {
      'jpg' || 'jpeg' || 'png' || 'webp' || 'heic' || 'heif' => true,
      _ => false,
    };
  }

  Future<void> _selectImageFile(XFile file, String statusKey) async {
    if (_isAnalyzing) return;
    if (!_isSupportedImageName(file.name) &&
        !_isSupportedImageName(file.path)) {
      debugPrint('不支持的图片格式: name=${file.name}, path=${file.path}');
      return;
    }

    final bytes = await file.readAsBytes();
    setState(() {
      _homeStatusKey = statusKey;
      _selectedImageBytes = bytes;
    });
  }

  void _navigateToResult() {
    if (_isAnalyzing) return;
    final imageBytes = _selectedImageBytes;
    if (imageBytes == null) {
      setState(() => _homeStatusKey = 'status_need_image');
      return;
    }

    HapticFeedback.heavyImpact(); // 启动识别的沉浸感反馈
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ResultPage(
          imageBytes: imageBytes,
          ollamaBaseUrl: _ollamaBaseUrl,
          ollamaModel: _ollamaModel,
          useDarkSkin: _useDarkSkin,
          useEnglish: _useEnglish,
          numCtx: _numCtx,
          numPredict: _numPredict,
          temperature: _temperature,
          maxImageEdge: _maxImageEdge,
          jpegQuality: _jpegQuality,
        ),
      ),
    );
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final skin = _skin;
    return Scaffold(
      backgroundColor: skin.background,
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              skin.background,
              skin.surface,
              skin.primarySoft.withOpacity(skin.isDark ? 0.10 : 0.16),
            ],
          ),
        ),
        child: SafeArea(
          bottom: false,
          child: _initializeControllerFuture == null
              ? _buildBodyContent(context, cameraReady: false)
              : FutureBuilder<void>(
                  future: _initializeControllerFuture,
                  builder: (context, snapshot) {
                    final cameraReady =
                        snapshot.connectionState == ConnectionState.done;
                    return _buildBodyContent(
                      context,
                      cameraReady: cameraReady && !snapshot.hasError,
                    );
                  },
                ),
        ),
      ),
      bottomNavigationBar: _buildBottomNavigation(skin),
    );
  }

  Widget _buildBodyContent(BuildContext context, {required bool cameraReady}) {
    final skin = _skin;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 34),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildGreetingHeader(skin),
              const SizedBox(height: 24),
              Text(
                _useEnglish ? 'Ceramic Archaeology' : '瓷语考古助手',
                style: TextStyle(
                  color: skin.primary,
                  fontSize: 34,
                  fontWeight: FontWeight.w800,
                  letterSpacing: _useEnglish ? 0 : 4,
                ),
              ),
              Text(
                'CeramiGuide AI',
                style: TextStyle(
                  color: skin.accent,
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 18),
              _buildHeroCard(skin),
              const SizedBox(height: 16),
              _buildFeaturePanel(skin),
              const SizedBox(height: 16),
              _buildActionButtons(skin, cameraReady),
              const SizedBox(height: 12),
              _buildStartButton(skin),
              const SizedBox(height: 14),
              Center(
                child: Text(
                  _homeStatusText,
                  textAlign: TextAlign.center,
                  style: TextStyle(color: skin.mutedText, fontSize: 13),
                ),
              ),
              const SizedBox(height: 24),
              _buildRecords(skin),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildGreetingHeader(_UiSkin skin) {
    return Row(
      children: [
        Container(
          width: 58,
          height: 58,
          padding: const EdgeInsets.all(3),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: skin.surface,
            border: Border.all(color: skin.border),
            boxShadow: [
              BoxShadow(
                color: skin.glow,
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: ClipOval(
            child: Image.asset('assets/mascot_xiaoci.png', fit: BoxFit.cover),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _useEnglish ? 'Hello, I am Xiao Ci' : '你好，我是小瓷',
                style: TextStyle(
                  color: skin.text,
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                _useEnglish ? 'Your AI ceramic guide' : '你的AI陶瓷导览助手',
                style: TextStyle(color: skin.mutedText, fontSize: 12),
              ),
            ],
          ),
        ),
        Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            _buildLanguageToggle(skin),
            const SizedBox(height: 8),
            _buildSkinToggle(skin),
          ],
        ),
      ],
    );
  }

  Widget _buildHeroCard(_UiSkin skin) {
    return Container(
      height: 350,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: skin.border.withOpacity(0.75)),
        boxShadow: [
          BoxShadow(
            color: skin.primary.withOpacity(skin.isDark ? 0.30 : 0.18),
            blurRadius: 26,
            offset: const Offset(0, 14),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(27),
        child: Stack(
          fit: StackFit.expand,
          children: [
            DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    skin.primary.withOpacity(0.92),
                    skin.primarySoft.withOpacity(0.72),
                    skin.elevatedSurface,
                  ],
                ),
              ),
            ),
            if (_selectedImageBytes == null)
              Positioned(
                left: -12,
                bottom: -36,
                width: 330,
                height: 330,
                child: Image.asset(
                  'assets/mascot_xiaoci.png',
                  fit: BoxFit.contain,
                  alignment: Alignment.bottomLeft,
                ),
              )
            else
              Positioned.fill(
                child: Hero(
                  tag: 'artifact_image',
                  child: Image.memory(_selectedImageBytes!, fit: BoxFit.cover),
                ),
              ),
            Positioned(
              top: 18,
              left: 18,
              child: _buildGlassPill(
                skin,
                icon: Icons.image_search_rounded,
                label: _selectedImageBytes == null
                    ? (_useEnglish ? 'Featured guide' : '推荐导览')
                    : _t('label_selected', _useEnglish),
              ),
            ),
            Positioned(
              top: 18,
              right: 18,
              child: _buildGlassPill(
                skin,
                icon: Icons.favorite_border_rounded,
                label: _useEnglish ? 'Favorite' : '收藏',
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGlassPill(
    _UiSkin skin, {
    required IconData icon,
    required String label,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: skin.surface.withOpacity(0.82),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: skin.accent.withOpacity(0.42)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: skin.primary),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: skin.text,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeaturePanel(_UiSkin skin) {
    final features = [
      (Icons.center_focus_strong_rounded, 'AI识别', '智能识别陶瓷'),
      (Icons.menu_book_rounded, '历史讲解', '了解文物故事'),
      (Icons.local_florist_rounded, '纹样解析', '探索纹样之美'),
      (Icons.account_balance_rounded, '相似器物', '发现相似文物'),
    ];
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 8),
      decoration: BoxDecoration(
        color: skin.surface.withOpacity(0.92),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: skin.border.withOpacity(0.75)),
        boxShadow: [
          BoxShadow(
            color: skin.glow,
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        children: features
            .map(
              (feature) => Expanded(
                child: Column(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: skin.primary,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(color: skin.glow, blurRadius: 12),
                        ],
                      ),
                      child: Icon(feature.$1, color: skin.background, size: 23),
                    ),
                    const SizedBox(height: 9),
                    Text(
                      feature.$2,
                      style: TextStyle(
                        color: skin.text,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      feature.$3,
                      textAlign: TextAlign.center,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: skin.mutedText, fontSize: 9),
                    ),
                  ],
                ),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _buildActionButtons(_UiSkin skin, bool cameraReady) {
    return Row(
      children: [
        Expanded(
          child: _buildActionCard(
            skin,
            icon: Icons.photo_camera_rounded,
            title: _t('take_photo', _useEnglish),
            subtitle: _useEnglish ? 'Identify by camera' : '拍照识别陶瓷',
            primary: true,
            onTap: (_isAnalyzing || !cameraReady) ? null : _takePicture,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildActionCard(
            skin,
            icon: Icons.photo_library_outlined,
            title: _t('select_image', _useEnglish),
            subtitle: _useEnglish ? 'Choose from library' : '从相册选择图片',
            onTap: _isAnalyzing ? null : _pickImageAndAnalyze,
          ),
        ),
      ],
    );
  }

  Widget _buildActionCard(
    _UiSkin skin, {
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback? onTap,
    bool primary = false,
  }) {
    final foreground = primary ? skin.background : skin.primary;
    return Material(
      color: primary ? skin.primary : skin.surface,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          height: 92,
          padding: const EdgeInsets.symmetric(horizontal: 18),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: skin.border),
          ),
          child: Row(
            children: [
              Icon(icon, color: foreground, size: 32),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        color: foreground,
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: foreground.withOpacity(0.70),
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStartButton(_UiSkin skin) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: (_isAnalyzing || _selectedImageBytes == null)
            ? null
            : _navigateToResult,
        icon: const Icon(Icons.auto_awesome_rounded),
        label: Padding(
          padding: const EdgeInsets.symmetric(vertical: 17),
          child: Column(
            children: [
              Text(
                _t('start_id', _useEnglish),
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                _useEnglish
                    ? 'Fast identification · Privacy protected'
                    : '快速识别，保护隐私',
                style: const TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w400,
                ),
              ),
            ],
          ),
        ),
        style: _primaryButtonStyle(skin, height: 66),
      ),
    );
  }

  Widget _buildRecords(_UiSkin skin) {
    final records = [
      (Icons.emoji_objects_rounded, '青釉莲花尊', '南北朝 · 青瓷'),
      (Icons.circle_outlined, '青花缠枝莲纹盘', '明代 · 景德镇窑'),
      (Icons.wine_bar_rounded, '青釉刻花瓶', '宋代 · 龙泉窑'),
      (Icons.local_florist_outlined, '粉彩花卉纹瓶', '清代 · 景德镇窑'),
    ];
    return Column(
      children: [
        Row(
          children: [
            Text(
              _useEnglish ? 'Recognition history' : '识别记录',
              style: TextStyle(
                color: skin.text,
                fontSize: 17,
                fontWeight: FontWeight.w800,
              ),
            ),
            const Spacer(),
            Text(
              _useEnglish ? 'View all  ›' : '查看全部  ›',
              style: TextStyle(color: skin.mutedText, fontSize: 12),
            ),
          ],
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: 142,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: records.length,
            separatorBuilder: (_, _) => const SizedBox(width: 12),
            itemBuilder: (context, index) {
              final record = records[index];
              return SizedBox(
                width: 132,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      height: 92,
                      decoration: BoxDecoration(
                        color: skin.surface,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: skin.border),
                      ),
                      child: Center(
                        child: index == 0
                            ? Image.asset(
                                'assets/mascot_xiaoci.png',
                                fit: BoxFit.contain,
                              )
                            : Icon(
                                record.$1,
                                size: 50,
                                color: skin.primarySoft,
                              ),
                      ),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      record.$2,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: skin.text,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      record.$3,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: skin.mutedText, fontSize: 9),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildBottomNavigation(_UiSkin skin) {
    final items = [
      (Icons.home_rounded, '首页'),
      (Icons.account_balance_outlined, '博物馆'),
      (Icons.menu_book_outlined, '知识库'),
      (Icons.person_outline_rounded, '我的'),
    ];
    return SafeArea(
      top: false,
      child: Container(
        height: 68,
        decoration: BoxDecoration(
          color: skin.surface,
          border: Border(top: BorderSide(color: skin.border.withOpacity(0.55))),
        ),
        child: Row(
          children: items
              .asMap()
              .entries
              .map(
                (entry) => Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        entry.value.$1,
                        color: entry.key == 0 ? skin.primary : skin.mutedText,
                        size: 23,
                      ),
                      const SizedBox(height: 3),
                      Text(
                        entry.value.$2,
                        style: TextStyle(
                          color: entry.key == 0 ? skin.primary : skin.mutedText,
                          fontSize: 10,
                          fontWeight: entry.key == 0
                              ? FontWeight.w800
                              : FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              )
              .toList(),
        ),
      ),
    );
  }

  Widget _buildLanguageToggle(_UiSkin skin) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: skin.surface,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: skin.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(3),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildLanguageChoice('中', !_useEnglish, skin),
            _buildLanguageChoice('EN', _useEnglish, skin),
          ],
        ),
      ),
    );
  }

  Widget _buildLanguageChoice(String label, bool selected, _UiSkin skin) {
    return InkWell(
      borderRadius: BorderRadius.circular(999),
      onTap: () => setState(() => _useEnglish = label == 'EN'),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        decoration: BoxDecoration(
          color: selected ? skin.primary : Colors.transparent,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? skin.background : skin.mutedText,
            fontWeight: FontWeight.w700,
            fontSize: 12,
          ),
        ),
      ),
    );
  }

  Widget _buildSkinToggle(_UiSkin skin) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: skin.surface,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: skin.border),
        boxShadow: [BoxShadow(color: skin.glow, blurRadius: 14)],
      ),
      child: Padding(
        padding: const EdgeInsets.all(3),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildSkinChoice('light', !_useDarkSkin, skin),
            _buildSkinChoice('dark', _useDarkSkin, skin),
          ],
        ),
      ),
    );
  }

  Widget _buildSkinChoice(String label, bool selected, _UiSkin skin) {
    return InkWell(
      borderRadius: BorderRadius.circular(999),
      onTap: () => setState(() => _useDarkSkin = label == 'dark'),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: selected ? skin.primary : Colors.transparent,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? skin.background : skin.mutedText,
            fontWeight: FontWeight.w700,
            fontSize: 12,
          ),
        ),
      ),
    );
  }

  ButtonStyle _primaryButtonStyle(_UiSkin skin, {double height = 48}) {
    return ButtonStyle(
      minimumSize: WidgetStateProperty.all(Size.fromHeight(height)),
      backgroundColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.pressed))
          return skin.primary.withOpacity(0.8);
        return skin.primary;
      }),
      foregroundColor: WidgetStateProperty.all(skin.background),
      elevation: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.pressed)) return 2;
        return 10; // 默认更高，产生厚重感
      }),
      side: WidgetStateProperty.all(BorderSide(color: skin.accent, width: 1.5)),
      shape: WidgetStateProperty.all(
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      shadowColor: WidgetStateProperty.all(skin.primary.withOpacity(0.7)),
      // 添加动态缩放效果
      padding: WidgetStateProperty.all(EdgeInsets.zero),
    ).copyWith(overlayColor: WidgetStateProperty.all(Colors.white10));
  }
}

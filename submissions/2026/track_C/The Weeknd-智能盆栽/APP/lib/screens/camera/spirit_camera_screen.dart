import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../../models/plant_friend.dart';
import '../../providers/config_provider.dart';
import '../../providers/tree_hole_provider.dart';
import '../../services/plant_recognition_service.dart';
import '../../widgets/pixel_plant_avatar.dart';

enum _CameraStage { idle, loading, result, error }

class SpiritCameraScreen extends StatefulWidget {
  const SpiritCameraScreen({super.key});

  @override
  State<SpiritCameraScreen> createState() => _SpiritCameraScreenState();
}

class _SpiritCameraScreenState extends State<SpiritCameraScreen> {
  final ImagePicker _picker = ImagePicker();
  final PlantRecognitionService _recognitionService =
      PlantRecognitionService();

  _CameraStage _stage = _CameraStage.idle;
  String? _imagePath;
  RecognitionResult? _result;
  String _statusMessage = '';
  bool _isAdding = false;

  Future<void> _pickImage(ImageSource source) async {
    try {
      final picked = await _picker.pickImage(
        source: source,
        maxWidth: 1024,
        maxHeight: 1024,
        imageQuality: 85,
      );
      if (!mounted) return;
      if (picked == null) return;

      final config = context.read<ConfigProvider>().config;
      setState(() {
        _imagePath = picked.path;
        _stage = _CameraStage.loading;
        _statusMessage = '正在鉴定植物灵魂...';
        _result = null;
      });

      final result = await _recognitionService.recognizePlant(
        picked.path,
        config,
      );

      if (!mounted) return;

      setState(() {
        _result = result;
        _stage = result.isSuccess ? _CameraStage.result : _CameraStage.error;
        _statusMessage = result.isSuccess
            ? '灵魂鉴定完成！'
            : '鉴定失败: ${result.errorMessage ?? "未知错误"}';
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _stage = _CameraStage.error;
        _statusMessage = '拍照或识别出错: $e';
        _result = RecognitionResult.failure(
          errorMessage: '$e',
          errorType: 'unexpected_error',
        );
      });
    }
  }

  void _reset() {
    setState(() {
      _stage = _CameraStage.idle;
      _imagePath = null;
      _result = null;
      _statusMessage = '';
    });
  }

  Future<void> _confirmAdd() async {
    if (_result?.profile == null) return;

    setState(() => _isAdding = true);

    try {
      final provider = context.read<TreeHoleProvider>();
      await provider.addCustomFriend(_result!.profile!);

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('已将 ${_result!.profile!.name} 添加为好友！'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      Navigator.pop(context);
    } catch (e) {
      if (!mounted) return;
      setState(() => _isAdding = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('添加好友失败: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('有灵相机'),
        actions: [
          if (_stage != _CameraStage.idle)
            IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: '重新拍照',
              onPressed: _reset,
            ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    switch (_stage) {
      case _CameraStage.idle:
        return _buildIdleView();
      case _CameraStage.loading:
        return _buildLoadingView();
      case _CameraStage.result:
        return _buildResultView();
      case _CameraStage.error:
        return _buildErrorView();
    }
  }

  Widget _buildIdleView() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                color: Colors.green.shade50,
                shape: BoxShape.circle,
                border: Border.all(
                  color: Colors.green.shade200,
                  width: 3,
                ),
              ),
              child: Icon(
                Icons.auto_awesome,
                size: 56,
                color: Colors.green.shade400,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              '有灵相机',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: Colors.green.shade800,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '拍下你身边的植物，\n为它赋予独特的灵魂人格',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.grey.shade600,
                fontSize: 15,
                height: 1.6,
              ),
            ),
            const SizedBox(height: 40),
            FilledButton.icon(
              onPressed: () => _pickImage(ImageSource.camera),
              icon: const Icon(Icons.camera_alt),
              label: const Text('拍照识别'),
              style: FilledButton.styleFrom(
                minimumSize: const Size(220, 52),
                textStyle: const TextStyle(fontSize: 16),
              ),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: () => _pickImage(ImageSource.gallery),
              icon: const Icon(Icons.photo_library),
              label: const Text('从相册选择'),
              style: OutlinedButton.styleFrom(
                minimumSize: const Size(220, 52),
                textStyle: const TextStyle(fontSize: 16),
              ),
            ),
            const SizedBox(height: 32),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.amber.shade50,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.amber.shade200),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline, color: Colors.amber.shade700),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      '需要使用支持视觉的本地模型才能识别植物图片。请确保在配置中已设置好模型路径。',
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.amber.shade800,
                        height: 1.5,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (_imagePath != null)
              Container(
                width: 200,
                height: 200,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  image: DecorationImage(
                    image: FileImage(File(_imagePath!)),
                    fit: BoxFit.cover,
                  ),
                ),
              ),
            const SizedBox(height: 32),
            CircularProgressIndicator(color: Colors.green.shade400),
            const SizedBox(height: 20),
            Text(
              _statusMessage,
              style: TextStyle(
                fontSize: 16,
                color: Colors.grey.shade700,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '正在分析植物特征，赋予灵魂人格...',
              style: TextStyle(
                fontSize: 13,
                color: Colors.grey.shade500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultView() {
    final profile = _result!.profile!;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          if (_imagePath != null)
            Container(
              width: double.infinity,
              height: 200,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                image: DecorationImage(
                  image: FileImage(File(_imagePath!)),
                  fit: BoxFit.cover,
                ),
              ),
            ),
          const SizedBox(height: 20),
          Card(
            elevation: 2,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  Row(
                    children: [
                      PixelPlantAvatar(plantId: profile.id, size: 64),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              profile.name,
                              style: const TextStyle(
                                fontSize: 20,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              _toneLabel(profile.tone),
                              style: TextStyle(
                                fontSize: 13,
                                color: Colors.grey.shade600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  const Divider(),
                  const SizedBox(height: 12),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      '性格标签',
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.grey.shade600,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: profile.tags
                        .map(
                          (tag) => Chip(
                            label: Text(tag),
                            backgroundColor: Colors.green.shade50,
                            side: BorderSide(color: Colors.green.shade200),
                          ),
                        )
                        .toList(),
                  ),
                  const SizedBox(height: 16),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      '个性签名',
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.grey.shade600,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: Colors.grey.shade50,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      profile.signature,
                      style: const TextStyle(
                        fontSize: 15,
                        height: 1.5,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            height: 52,
            child: FilledButton.icon(
              onPressed: _isAdding ? null : _confirmAdd,
              icon: _isAdding
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.person_add_alt_1),
              label: Text(_isAdding ? '添加中...' : '添加为好友'),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            height: 48,
            child: OutlinedButton.icon(
              onPressed: _isAdding ? null : _reset,
              icon: const Icon(Icons.refresh),
              label: const Text('重新拍照'),
            ),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildErrorView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const SizedBox(height: 40),
          Icon(
            Icons.error_outline,
            size: 64,
            color: Colors.red.shade300,
          ),
          const SizedBox(height: 20),
          Text(
            '灵魂鉴定失败',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              color: Colors.red.shade400,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            _statusMessage,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey.shade700,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 24),
          if (_result != null)
            _buildErrorDetails(_result!),
          const SizedBox(height: 32),
          SizedBox(
            width: double.infinity,
            height: 52,
            child: FilledButton.icon(
              onPressed: _reset,
              icon: const Icon(Icons.camera_alt),
              label: const Text('重新拍照'),
            ),
          ),
          const SizedBox(height: 12),
          if (_imagePath != null)
            SizedBox(
              width: double.infinity,
              height: 48,
              child: OutlinedButton.icon(
                onPressed: () => _pickImage(ImageSource.gallery),
                icon: const Icon(Icons.photo_library),
                label: const Text('换一张照片试试'),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildErrorDetails(RecognitionResult result) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.bug_report, size: 18, color: Colors.grey.shade600),
              const SizedBox(width: 6),
              Text(
                '错误日志',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey.shade700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _logRow('错误类型', _errorTypeLabel(result.errorType ?? 'unknown')),
          _logRow('错误信息', result.errorMessage ?? '未知'),
          if (result.rawResponse != null) ...[
            const SizedBox(height: 8),
            Text(
              '模型原始输出:',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
              ),
            ),
            const SizedBox(height: 4),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.grey.shade300),
              ),
              constraints: const BoxConstraints(maxHeight: 200),
              child: SingleChildScrollView(
                child: SelectableText(
                  result.rawResponse!,
                  style: TextStyle(
                    fontSize: 12,
                    fontFamily: 'monospace',
                    color: Colors.grey.shade800,
                    height: 1.4,
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _logRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 70,
            child: Text(
              '$label:',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade600,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade800,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _errorTypeLabel(String type) {
    switch (type) {
      case 'json_parse_error':
        return '格式错误 - 模型输出不是有效JSON';
      case 'missing_field':
        return '字段缺失 - 模型输出缺少必要字段';
      case 'recognition_failed':
        return '识别失败 - 模型未能识别到植物';
      case 'model_call_error':
        return '调用失败 - 模型调用过程出错';
      case 'unexpected_error':
        return '意外错误 - 发生了未预期的异常';
      default:
        return '未知错误类型: $type';
    }
  }

  String _toneLabel(PlantTone tone) {
    switch (tone) {
      case PlantTone.tsundere:
        return '傲娇';
      case PlantTone.observer:
        return '腹黑';
      case PlantTone.cool:
        return '高冷';
      case PlantTone.zen:
        return '佛系';
      case PlantTone.reliable:
        return '可靠';
      case PlantTone.warm:
        return '温柔';
      case PlantTone.princess:
        return '贵气';
      case PlantTone.sunshine:
        return '阳光';
      case PlantTone.stoic:
        return '坚韧';
      case PlantTone.poetic:
        return '诗意';
      case PlantTone.money:
        return '财迷';
      case PlantTone.dramatic:
        return '抓马';
      case PlantTone.romantic:
        return '浪漫';
      case PlantTone.playful:
        return '活泼';
      case PlantTone.scholar:
        return '学霸';
      case PlantTone.sharp:
        return '犀利';
    }
  }
}

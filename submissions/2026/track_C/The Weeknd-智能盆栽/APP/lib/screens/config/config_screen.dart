import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:permission_handler/permission_handler.dart';
import '../../providers/config_provider.dart';
import '../../providers/chat_provider.dart';
import '../../services/local_model_coordinator.dart';

class ConfigScreen extends StatefulWidget {
  const ConfigScreen({super.key});

  @override
  State<ConfigScreen> createState() => _ConfigScreenState();
}

class _ConfigScreenState extends State<ConfigScreen> {
  final _urlController = TextEditingController();
  final _modelController = TextEditingController();
  final _keyController = TextEditingController();
  final _systemPromptController = TextEditingController();
  final _hardwareIpController = TextEditingController();
  final _hardwarePortController = TextEditingController();
  final _localModelPathController = TextEditingController();
  final _localMmprojPathController = TextEditingController();
  final _assistantNicknameController = TextEditingController();
  final _contextSizeController = TextEditingController();
  final _threadsController = TextEditingController();
  bool _enableThinking = false;

  List<String> _availableModels = [];
  bool _isScanning = false;

  @override
  void initState() {
    super.initState();
    // 初始化时从 Provider 获取当前配置并填充
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final configProvider = Provider.of<ConfigProvider>(
        context,
        listen: false,
      );
      if (!configProvider.isLoading) {
        _urlController.text = configProvider.config.apiUrl;
        _modelController.text = configProvider.config.modelName;
        _keyController.text = configProvider.config.apiKey;
        _systemPromptController.text = configProvider.config.systemPrompt;
        _hardwareIpController.text = configProvider.config.hardwareIp;
        _hardwarePortController.text = configProvider.config.hardwarePort;
        _localModelPathController.text = configProvider.config.localModelPath;
        _localMmprojPathController.text = configProvider.config.localMmprojPath;
        _assistantNicknameController.text = configProvider.config.assistantNickname;
        _contextSizeController.text = configProvider.config.contextSize
            .toString();
        _threadsController.text = configProvider.config.threads.toString();
        setState(() {
          _enableThinking = configProvider.config.enableThinking;
        });

        // 初始化时扫描模型目录
        _scanModels();
      }
    });
  }

  Future<void> _scanModels() async {
    setState(() {
      _isScanning = true;
    });

    try {
      // 显式请求存储权限
      if (Platform.isAndroid) {
        await LocalModelCoordinator.ensureStoragePermissions();
        final status = await Permission.storage.status;
        final manageStatus = await Permission.manageExternalStorage.status;

        if (!status.isGranted && !manageStatus.isGranted) {
          if (mounted) {
            ScaffoldMessenger.of(
              context,
            ).showSnackBar(const SnackBar(content: Text('需要存储权限才能扫描模型文件')));
          }
          return;
        }
      }

      // 常见的下载目录路径
      final List<String> possiblePaths = [
        '/storage/emulated/0/Download',
        '/sdcard/Download',
      ];

      List<String> ggufFiles = [];

      for (String path in possiblePaths) {
        final dir = Directory(path);
        if (await dir.exists()) {
          final List<FileSystemEntity> entities = await dir
              .list(recursive: false)
              .toList();
          final files = entities
              .whereType<File>()
              .where((file) => file.path.toLowerCase().endsWith('.gguf'))
              .map((file) => file.path)
              .toList();
          ggufFiles.addAll(files);
        }
      }

      // 去重
      ggufFiles = ggufFiles.toSet().toList();

      setState(() {
        _availableModels = ggufFiles;
        // 只有当路径确实是一个 .gguf 文件时才加入列表
        if (_localModelPathController.text.isNotEmpty &&
            _localModelPathController.text.toLowerCase().endsWith('.gguf') &&
            !_availableModels.contains(_localModelPathController.text)) {
          _availableModels.insert(0, _localModelPathController.text);
        }

        if (_localMmprojPathController.text.isNotEmpty &&
            _localMmprojPathController.text.toLowerCase().endsWith('.gguf') &&
            !_availableModels.contains(_localMmprojPathController.text)) {
          _availableModels.insert(0, _localMmprojPathController.text);
        }
      });
    } catch (e) {
      debugPrint('扫描模型出错: $e');
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('扫描出错: $e')));
      }
    } finally {
      if (mounted) {
        setState(() {
          _isScanning = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _urlController.dispose();
    _modelController.dispose();
    _keyController.dispose();
    _systemPromptController.dispose();
    _hardwareIpController.dispose();
    _hardwarePortController.dispose();
    _localModelPathController.dispose();
    _localMmprojPathController.dispose();
    _assistantNicknameController.dispose();
    _contextSizeController.dispose();
    _threadsController.dispose();
    super.dispose();
  }

  void _saveConfig() {
    final configProvider = Provider.of<ConfigProvider>(context, listen: false);
    configProvider.updateConfig(
      _urlController.text,
      _modelController.text,
      _keyController.text,
      _systemPromptController.text,
      configProvider.config.ownPlantId,
      _hardwareIpController.text,
      _hardwarePortController.text,
      _localModelPathController.text,
      _localMmprojPathController.text,
      _assistantNicknameController.text,
      _enableThinking,
      int.tryParse(_contextSizeController.text) ?? 4096,
      int.tryParse(_threadsController.text) ?? 6,
      false,
      'M1',
    );
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('配置已保存')));
  }

  @override
  Widget build(BuildContext context) {
    final configProvider = Provider.of<ConfigProvider>(context);

    if (configProvider.isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return Scaffold(
      appBar: AppBar(title: const Text('模型与硬件配置')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Gemma 4 / 兼容接口配置 (远程可选)',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _urlController,
              decoration: const InputDecoration(
                labelText: 'API 地址（可选）',
                hintText: '例如本地网关或兼容 OpenAI 的服务地址',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _modelController,
              decoration: const InputDecoration(
                labelText: '模型名称',
                hintText: 'gemma-4-E2B-it-GGUF',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _keyController,
              decoration: const InputDecoration(
                labelText: 'API Key（可留空）',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _systemPromptController,
              maxLines: 5,
              minLines: 3,
              decoration: const InputDecoration(
                labelText: '系统提示词',
                hintText: '例如：你是一个温柔、专业的植物养护助手，回答要口语化且简洁。',
                helperText: '会作为 system message 发送给大模型，用于角色设定和回答风格控制',
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _assistantNicknameController,
              decoration: const InputDecoration(
                labelText: 'AI 助手昵称',
                hintText: '给你的植物助手起个名字吧',
                helperText: '为你的 AI 助手设定一个自定义名字，留空则显示为"AI 助手"',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            Center(
              child: OutlinedButton.icon(
                onPressed: () {
                  final chatProvider = context.read<ChatProvider>();
                  chatProvider.clearAssistantMemory();
                  ScaffoldMessenger.of(
                    // ignore: use_build_context_synchronously
                    context,
                  ).showSnackBar(
                    const SnackBar(content: Text('已清除植物助手的记忆和对话历史')),
                  );
                },
                icon: const Icon(Icons.delete_outline),
                label: const Text('清除植物助手记忆'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.orange,
                  side: const BorderSide(color: Colors.orange),
                ),
              ),
            ),
            const SizedBox(height: 32),
            const Text(
              'Gemma 4 端侧配置 (推荐)',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),

            // 下拉选择或手动输入模型路径
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _localModelPathController,
                    decoration: const InputDecoration(
                      labelText: '本地 GGUF 模型路径',
                      hintText: '/storage/emulated/0/Download/gemma-4-E2B-it-GGUF.gguf',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                if (_isScanning)
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 16.0),
                    child: SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                else
                  IconButton(
                    icon: const Icon(Icons.refresh),
                    onPressed: _scanModels,
                    tooltip: '重新扫描 Download 目录',
                  ),
              ],
            ),
            if (_availableModels.isNotEmpty) ...[
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                isExpanded: true,
                initialValue:
                    _availableModels.contains(_localModelPathController.text)
                    ? _localModelPathController.text
                    : null,
                hint: const Text('选择已扫描到的 Gemma 4 / 兼容语言模型'),
                items: _availableModels.map((path) {
                  return DropdownMenuItem(
                    value: path,
                    child: Text(
                      path.split('/').last,
                      overflow: TextOverflow.ellipsis,
                    ),
                  );
                }).toList(),
                onChanged: (val) {
                  if (val != null) {
                    setState(() {
                      _localModelPathController.text = val;
                    });
                  }
                },
              ),
            ],

            const SizedBox(height: 16),
            TextField(
              controller: _localMmprojPathController,
              decoration: const InputDecoration(
                labelText: '本地 mmproj 视觉模型路径（多模态必填）',
                hintText: '/storage/emulated/0/Download/mmproj-model-f16.gguf',
                helperText: '使用 Gemma 4 多模态版本进行植物识别时，必须提供对应 mmproj 文件',
                border: OutlineInputBorder(),
              ),
            ),

            if (_availableModels.isNotEmpty) ...[
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                isExpanded: true,
                initialValue:
                    _availableModels.contains(_localMmprojPathController.text)
                    ? _localMmprojPathController.text
                    : null,
                hint: const Text('选择已扫描到的视觉投影器 (mmproj)'),
                items: _availableModels.map((path) {
                  return DropdownMenuItem(
                    value: path,
                    child: Text(
                      path.split('/').last,
                      overflow: TextOverflow.ellipsis,
                    ),
                  );
                }).toList(),
                onChanged: (val) {
                  if (val != null) {
                    setState(() {
                      _localMmprojPathController.text = val;
                    });
                  }
                },
              ),
            ],

            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _contextSizeController,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Context Size (-c)',
                      hintText: '4096',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: TextField(
                    controller: _threadsController,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Threads (-t)',
                      hintText: '6',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            SwitchListTile(
              title: const Text('开启思考模式 (Reasoning)'),
              subtitle: const Text('仅在所选 Gemma 4 变体支持时启用；比赛演示建议默认关闭'),
              value: _enableThinking,
              onChanged: (val) {
                setState(() {
                  _enableThinking = val;
                });
              },
              contentPadding: EdgeInsets.zero,
            ),

            const SizedBox(height: 32),
            const Text(
              '硬件控制配置 (ESP32-S3)',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _hardwareIpController,
              decoration: const InputDecoration(
                labelText: '硬件 IP 地址',
                hintText: '192.168.1.100',
                helperText: '不提供默认值，连接成功后请按实际局域网地址填写',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _hardwarePortController,
              decoration: const InputDecoration(
                labelText: '硬件端口',
                hintText: '80 (ESP32 默认)',
              border: OutlineInputBorder(),
              helperText: '硬件 WebServer 默认监听 80 端口',
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _saveConfig,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
              child: const Text('保存配置', style: TextStyle(fontSize: 16)),
            ),
          ],
        ),
      ),
    );
  }
}

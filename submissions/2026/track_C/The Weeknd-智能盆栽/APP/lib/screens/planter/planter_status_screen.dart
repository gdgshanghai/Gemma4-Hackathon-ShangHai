import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/config_provider.dart';
import '../../providers/memory_provider.dart';
import '../../services/planter_service.dart';
import '../../services/quote_service.dart';
import '../../models/planter_data.dart';

class PlanterStatusScreen extends StatefulWidget {
  const PlanterStatusScreen({super.key});

  @override
  State<PlanterStatusScreen> createState() => _PlanterStatusScreenState();
}

class _PlanterStatusScreenState extends State<PlanterStatusScreen> {
  final PlanterService _planterService = PlanterService();
  PlanterData? _data;
  bool _isRefreshing = false;
  bool _isWaking = false;
  String? _error;
  Timer? _timer;

  final Map<String, bool> _fieldRefreshing = {
    'temperature': false,
    'moisture': false,
    'emotion': false,
    'sleep': false,
  };

  String _getEmotionText(int emotionId) {
    switch (emotionId) {
      case 0: return '平静';
      case 1: return '开心';
      case 2: return '生气';
      case 3: return '悲伤';
      case 4: return '惊讶';
      case 5: return '口渴';
      case 6: return '冷';
      case 7: return '热';
      default: return '未知状态';
    }
  }

  @override
  void initState() {
    super.initState();
    _fetchData(refreshAll: true);
    _timer = Timer.periodic(const Duration(seconds: 5), (_) {
      _fetchData(refreshAll: true);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _fetchData({bool refreshAll = false}) async {
    if (!mounted) return;
    if (_isRefreshing) return;

    setState(() {
      _isRefreshing = true;
      if (refreshAll) {
        _fieldRefreshing.updateAll((_, __) => true);
      }
    });

    final config = Provider.of<ConfigProvider>(context, listen: false).config;

    try {
      final data = await _planterService.fetchPlanterData(config);
      if (mounted) {
        setState(() {
          _data = data;
          _error = null;
          _isRefreshing = false;
          if (refreshAll) {
            _fieldRefreshing.updateAll((_, __) => false);
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _isRefreshing = false;
          if (refreshAll) {
            _fieldRefreshing.updateAll((_, __) => false);
          }
        });
      }
    }
  }

  Future<void> _refreshSingleField(String key) async {
    if (!mounted || _isRefreshing) return;

    setState(() {
      _fieldRefreshing[key] = true;
    });

    final config = Provider.of<ConfigProvider>(context, listen: false).config;

    try {
      final data = await _planterService.fetchPlanterData(config);
      if (mounted) {
        setState(() {
          _data = data;
          _error = null;
          _fieldRefreshing[key] = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _fieldRefreshing[key] = false;
        });
      }
    }
  }

  Future<void> _wakeUpPlant() async {
    if (!mounted || _isWaking) return;

    setState(() {
      _isWaking = true;
    });

    final config = Provider.of<ConfigProvider>(context, listen: false).config;
    final memoryProvider = Provider.of<MemoryProvider>(context, listen: false);
    final memoryContext = memoryProvider.buildMemoryContext(config.ownPlantId);
    final quoteService = QuoteService();

    try {
      final quote = await quoteService.generateQuote(
        config: config,
        memoryContext: memoryContext,
      );

      if (!mounted) return;

      if (quote == null || quote.isEmpty) {
        setState(() { _isWaking = false; });
        debugPrint('[WakeUp] 语录生成失败，quote=$quote');
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('唤醒失败：语录生成失败')),
        );
        return;
      }

      final success = await quoteService.pushQuote(quote, config);
      if (!mounted) return;

      setState(() { _isWaking = false; });

      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('已唤醒: "$quote"')),
        );
        await Future.delayed(const Duration(seconds: 1));
        if (mounted) {
          _fetchData(refreshAll: true);
        }
      } else {
        debugPrint('[WakeUp] 推送失败，quote=$quote');
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('唤醒失败，请检查网络连接')),
        );
      }
    } catch (e) {
      debugPrint('[WakeUp] 唤醒异常: $e');
      if (mounted) {
        setState(() { _isWaking = false; });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('唤醒失败: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('智能盆栽状态'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isRefreshing
                ? null
                : () => _fetchData(refreshAll: true),
          )
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_data == null && _isRefreshing) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null && _data == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Text(
            '获取状态失败:\n$_error',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.red),
          ),
        ),
      );
    }

    if (_data == null) {
      return const Center(child: Text('暂无数据'));
    }

    return RefreshIndicator(
      onRefresh: () => _fetchData(refreshAll: true),
      child: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          _buildStatusCard(
            title: '环境温度',
            value: _fieldRefreshing['temperature'] == true
                ? '获取中...'
                : '${_data!.temperature.toStringAsFixed(1)} °C',
            icon: Icons.thermostat,
            color: Colors.orange,
            onRefresh: () => _refreshSingleField('temperature'),
          ),
          _buildStatusCard(
            title: '土壤湿度 (RAW)',
            value: _fieldRefreshing['moisture'] == true
                ? '获取中...'
                : '${_data!.moisture}',
            icon: Icons.water_drop,
            color: Colors.blue,
            onRefresh: () => _refreshSingleField('moisture'),
          ),
          _buildStatusCard(
            title: '当前情绪',
            value: _fieldRefreshing['emotion'] == true
                ? '获取中...'
                : _getEmotionText(_data!.emotion),
            icon: Icons.face,
            color: Colors.purple,
            onRefresh: () => _refreshSingleField('emotion'),
          ),
          _buildStatusCard(
            title: '休眠状态',
            value: _fieldRefreshing['sleep'] == true
                ? '获取中...'
                : (_data!.isSleeping ? '休眠中' : '清醒'),
            icon: _data!.isSleeping ? Icons.bedtime : Icons.wb_sunny,
            color: _data!.isSleeping ? Colors.indigo : Colors.amber,
            onRefresh: () => _refreshSingleField('sleep'),
          ),
          if (_data!.isSleeping) ...[
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isWaking ? null : _wakeUpPlant,
                icon: _isWaking
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.alarm, size: 20),
                label: Text(_isWaking ? '正在唤醒...' : '唤醒植物'),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatusCard({
    required String title,
    required String value,
    required IconData icon,
    required Color color,
    required VoidCallback onRefresh,
  }) {
    final isRefreshingValue = value.contains('获取中');
    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 16.0),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withValues(alpha: 0.2),
          child: Icon(icon, color: color),
        ),
        title: Text(title),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              isRefreshingValue ? '获取中' : value,
              style: TextStyle(
                fontSize: isRefreshingValue ? 14 : 14,
                fontWeight: FontWeight.bold,
                color: isRefreshingValue ? Colors.grey : null,
              ),
            ),
            if (isRefreshingValue) ...[
              const SizedBox(width: 8),
              SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: color,
                ),
              ),
            ] else
              IconButton(
                icon: const Icon(Icons.refresh),
                iconSize: 20,
                onPressed: onRefresh,
              ),
          ],
        ),
      ),
    );
  }
}

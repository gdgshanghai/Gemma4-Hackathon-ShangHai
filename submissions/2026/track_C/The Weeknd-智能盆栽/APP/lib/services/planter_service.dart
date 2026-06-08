import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../models/app_config.dart';
import '../models/planter_data.dart';

class PlanterService {
  static const int timeoutSeconds = 6;
  static const int retryCount = 3;

  Future<PlanterData> fetchPlanterData(AppConfig config) async {
    final ip = config.hardwareIp;
    final port = config.hardwarePort;
    if (ip.isEmpty || port.isEmpty) {
      throw Exception('未配置硬件 IP 或端口');
    }

    final url = Uri.parse('http://$ip:$port/api/data');
    debugPrint('[PlanterService] Fetching planter data from: $url');

    Object? lastError;
    for (int attempt = 1; attempt <= retryCount; attempt++) {
      try {
        final response = await http
            .get(url)
            .timeout(Duration(seconds: timeoutSeconds));

        if (response.statusCode == 200) {
          final jsonMap = jsonDecode(response.body) as Map<String, dynamic>;
          final data = PlanterData.fromJson(jsonMap);
          debugPrint('[PlanterService] Success: ${response.body}');
          return data;
        } else {
          lastError = 'HTTP ${response.statusCode}: ${response.body}';
          debugPrint('[PlanterService] Attempt $attempt failed: $lastError');
        }
      } catch (e) {
        lastError = e.toString();
        debugPrint('[PlanterService] Attempt $attempt error: $e');
      }

      if (attempt < retryCount) {
        await Future.delayed(const Duration(seconds: 2));
      }
    }

    throw Exception(
      '获取硬件数据失败 (已重试 $retryCount 次): $lastError\n'
      '当前地址: $ip:$port\n'
      '请确认：1.硬件已上电并连接WiFi 2.手机和硬件在同一局域网 3.配置中的IP地址正确'
    );
  }

  Future<bool> wakeUp(AppConfig config) async {
    final ip = config.hardwareIp;
    final port = config.hardwarePort;
    if (ip.isEmpty || port.isEmpty) return false;

    final uri = Uri.parse('http://$ip:$port/api/wake');
    try {
      final response = await http
          .get(uri)
          .timeout(Duration(seconds: timeoutSeconds));
      return response.statusCode == 200;
    } catch (e) {
      debugPrint('[PlanterService] wakeUp error: $e');
      return false;
    }
  }

  Future<bool> sendQuote(AppConfig config, String quote) async {
    final ip = config.hardwareIp;
    final port = config.hardwarePort;
    if (ip.isEmpty || port.isEmpty) return false;

    final uri = Uri.parse(
      'http://$ip:$port/api/quote?text=${Uri.encodeComponent(quote)}',
    );

    try {
      final response = await http
          .get(uri)
          .timeout(Duration(seconds: timeoutSeconds));
      return response.statusCode == 200;
    } catch (e) {
      debugPrint('[PlanterService] sendQuote error: $e');
      return false;
    }
  }
}

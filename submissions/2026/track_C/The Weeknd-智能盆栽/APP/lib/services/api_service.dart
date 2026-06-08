import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/app_config.dart';
import '../models/message.dart';

class ApiService {
  Stream<String> sendMessageStream(List<Message> messages, AppConfig config) {
    return sendRawMessageStream(messages.map((m) => m.toJson()).toList(), config);
  }

  Stream<String> sendRawMessageStream(List<Map<String, dynamic>> messages, AppConfig config) {
    final url = Uri.parse(config.apiUrl);

    final headers = {
      'Content-Type': 'application/json',
      if (config.apiKey.isNotEmpty) 'Authorization': 'Bearer ${config.apiKey}',
    };

    final body = jsonEncode({
      'model': config.modelName,
      'messages': messages,
      'stream': true,
    });

    final client = http.Client();
    final controller = StreamController<String>();

    client.send(http.Request('POST', url)
      ..headers.addAll(headers)
      ..body = body)
        .then((streamedResponse) {
          if (streamedResponse.statusCode != 200) {
            controller.addError(
              '请求失败: 状态码 ${streamedResponse.statusCode}',
            );
            controller.close();
            client.close();
            return;
          }

          final lineStream = streamedResponse.stream
              .transform(utf8.decoder)
              .transform(const LineSplitter());

          lineStream.listen(
            (line) {
              if (line.isEmpty || line.startsWith(':')) return;
              if (!line.startsWith('data: ')) return;

              final jsonStr = line.substring(6).trim();
              if (jsonStr == '[DONE]') return;

              try {
                final data = jsonDecode(jsonStr);
                final choices = data['choices'] as List?;
                if (choices != null && choices.isNotEmpty) {
                  final delta = choices[0]['delta'];
                  if (delta != null && delta['content'] != null) {
                    controller.add(delta['content'] as String);
                  }
                }
              } catch (_) {}
            },
            onDone: () {
              controller.close();
              client.close();
            },
            onError: (e) {
              controller.addError('流读取错误: $e');
              controller.close();
              client.close();
            },
          );
        })
        .catchError((e) {
          controller.addError('网络请求错误: $e');
          controller.close();
          client.close();
        });

    return controller.stream;
  }
}

class Message {
  final String role;
  String content;
  final DateTime timestamp;
  final List<String> imagePaths;

  Message({
    required this.role,
    required this.content,
    required this.timestamp,
    List<String>? imagePaths,
  }) : imagePaths = imagePaths ?? const [];

  Map<String, dynamic> toJson() {
    if (imagePaths.isNotEmpty) {
      final parts = <Map<String, dynamic>>[];
      if (content.trim().isNotEmpty) {
        parts.add({'type': 'text', 'text': content});
      }
      for (final path in imagePaths) {
        parts.add({
          'type': 'image_url',
          'image_url': {'url': 'file://$path'},
        });
      }
      return {'role': role, 'content': parts};
    }
    return {'role': role, 'content': content};
  }
}

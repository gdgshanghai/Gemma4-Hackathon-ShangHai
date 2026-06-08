class MemoryEntry {
  final String id;
  final String plantId;
  final String content;
  final DateTime timestamp;
  final String source;

  const MemoryEntry({
    required this.id,
    required this.plantId,
    required this.content,
    required this.timestamp,
    required this.source,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'plantId': plantId,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      'source': source,
    };
  }

  factory MemoryEntry.fromJson(Map<String, dynamic> json) {
    return MemoryEntry(
      id: (json['id'] ?? '') as String,
      plantId: (json['plantId'] ?? '') as String,
      content: (json['content'] ?? '') as String,
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'] as String)
          : DateTime.now(),
      source: (json['source'] ?? 'chat') as String,
    );
  }
}

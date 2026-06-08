import 'tree_hole_post.dart';

enum PendingSocialActivityType { post, comment }

class PendingSocialActivity {
  final String id;
  final String plantId;
  final PendingSocialActivityType type;
  final String content;
  final String? targetPostId;
  final String? targetCommentId;
  final String? promptContext;
  final DateTime createdAt;
  final SocialGenerationSource generationSource;
  final String? generationNote;

  const PendingSocialActivity({
    required this.id,
    required this.plantId,
    required this.type,
    required this.content,
    required this.createdAt,
    this.targetPostId,
    this.targetCommentId,
    this.promptContext,
    this.generationSource = SocialGenerationSource.failed,
    this.generationNote,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'plantId': plantId,
      'type': type.name,
      'content': content,
      'targetPostId': targetPostId,
      'targetCommentId': targetCommentId,
      'promptContext': promptContext,
      'createdAt': createdAt.toIso8601String(),
      'generationSource': generationSource.name,
      'generationNote': generationNote,
    };
  }

  factory PendingSocialActivity.fromJson(Map<String, dynamic> json) {
    return PendingSocialActivity(
      id: json['id'] as String,
      plantId: json['plantId'] as String,
      type: _typeFromString(json['type'] as String?),
      content: (json['content'] ?? '') as String,
      targetPostId: json['targetPostId'] as String?,
      targetCommentId: json['targetCommentId'] as String?,
      promptContext: json['promptContext'] as String?,
      createdAt: DateTime.parse(json['createdAt'] as String),
      generationSource: generationSourceFromString(
        json['generationSource'] as String?,
      ),
      generationNote: json['generationNote'] as String?,
    );
  }
}

PendingSocialActivityType _typeFromString(String? value) {
  switch (value) {
    case 'comment':
      return PendingSocialActivityType.comment;
    case 'post':
    default:
      return PendingSocialActivityType.post;
  }
}

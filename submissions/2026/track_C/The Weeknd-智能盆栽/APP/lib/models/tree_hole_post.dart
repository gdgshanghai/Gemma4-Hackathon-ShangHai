enum PostAuthorType { user, plant }

enum MomentVisibility { friends, private }

enum SocialGenerationSource { user, localModel, apiModel, failed, legacy }

class MomentComment {
  final String id;
  final String authorId;
  final String authorName;
  final PostAuthorType authorType;
  final String content;
  final DateTime timestamp;
  final String? parentCommentId;
  final String? replyToCommentId;
  final String? replyToAuthorName;
  final int depth;
  final SocialGenerationSource generationSource;
  final String? generationNote;

  MomentComment({
    required this.id,
    required this.authorId,
    required this.authorName,
    required this.authorType,
    required this.content,
    required this.timestamp,
    this.parentCommentId,
    this.replyToCommentId,
    this.replyToAuthorName,
    this.depth = 0,
    this.generationSource = SocialGenerationSource.user,
    this.generationNote,
  });

  bool get isReply => parentCommentId != null;

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'authorId': authorId,
      'authorName': authorName,
      'authorType': authorType.name,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      'parentCommentId': parentCommentId,
      'replyToCommentId': replyToCommentId,
      'replyToAuthorName': replyToAuthorName,
      'depth': depth,
      'generationSource': generationSource.name,
      'generationNote': generationNote,
    };
  }

  factory MomentComment.fromJson(Map<String, dynamic> json) {
    return MomentComment(
      id: json['id'] as String,
      authorId: (json['authorId'] ?? 'user') as String,
      authorName: (json['authorName'] ?? '我') as String,
      authorType: _authorTypeFromString(json['authorType'] as String?),
      content: (json['content'] ?? '') as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
      parentCommentId: json['parentCommentId'] as String?,
      replyToCommentId: json['replyToCommentId'] as String?,
      replyToAuthorName: json['replyToAuthorName'] as String?,
      depth: json['depth'] as int? ?? 0,
      generationSource: _commentGenerationSourceFromJson(json),
      generationNote: json['generationNote'] as String?,
    );
  }
}

class TreeHolePost {
  final String id;
  final String authorId;
  final String authorName;
  final PostAuthorType authorType;
  final String content;
  final List<String> imagePaths;
  final DateTime timestamp;
  final MomentVisibility visibility;
  final List<MomentComment> comments;
  final SocialGenerationSource generationSource;
  final String? generationNote;

  TreeHolePost({
    required this.id,
    required this.authorId,
    required this.authorName,
    required this.authorType,
    required this.content,
    required this.imagePaths,
    required this.timestamp,
    this.visibility = MomentVisibility.friends,
    List<MomentComment>? comments,
    this.generationSource = SocialGenerationSource.user,
    this.generationNote,
  }) : comments = comments ?? [];

  bool get isUserPost => authorType == PostAuthorType.user;
  bool get isPrivate => visibility == MomentVisibility.private;

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'authorId': authorId,
      'authorName': authorName,
      'authorType': authorType.name,
      'content': content,
      'imagePaths': imagePaths,
      'timestamp': timestamp.toIso8601String(),
      'visibility': visibility.name,
      'comments': comments.map((e) => e.toJson()).toList(),
      'generationSource': generationSource.name,
      'generationNote': generationNote,
    };
  }

  factory TreeHolePost.fromJson(Map<String, dynamic> json) {
    final commentsJson = (json['comments'] as List<dynamic>? ?? [])
        .cast<Map<String, dynamic>>();
    final comments = commentsJson
        .map((e) => MomentComment.fromJson(e))
        .toList();

    return TreeHolePost(
      id: json['id'] as String,
      authorId: (json['authorId'] ?? 'user') as String,
      authorName: (json['authorName'] ?? '我') as String,
      authorType: _authorTypeFromString(json['authorType'] as String?),
      content: (json['content'] ?? '') as String,
      imagePaths: List<String>.from(json['imagePaths'] ?? []),
      timestamp: DateTime.parse(json['timestamp'] as String),
      visibility: _visibilityFromString(json['visibility'] as String?),
      comments: comments,
      generationSource: _postGenerationSourceFromJson(json),
      generationNote: json['generationNote'] as String?,
    );
  }
}

PostAuthorType _authorTypeFromString(String? value) {
  switch (value) {
    case 'plant':
      return PostAuthorType.plant;
    case 'user':
    default:
      return PostAuthorType.user;
  }
}

MomentVisibility _visibilityFromString(String? value) {
  switch (value) {
    case 'private':
      return MomentVisibility.private;
    case 'friends':
    default:
      return MomentVisibility.friends;
  }
}

SocialGenerationSource generationSourceFromString(String? value) {
  switch (value) {
    case 'localModel':
      return SocialGenerationSource.localModel;
    case 'apiModel':
      return SocialGenerationSource.apiModel;
    case 'failed':
      return SocialGenerationSource.failed;
    case 'legacy':
      return SocialGenerationSource.legacy;
    case 'user':
    default:
      return SocialGenerationSource.user;
  }
}

SocialGenerationSource _commentGenerationSourceFromJson(
  Map<String, dynamic> json,
) {
  final raw = json['generationSource'] as String?;
  if (raw != null && raw.isNotEmpty) {
    return generationSourceFromString(raw);
  }
  final authorType = _authorTypeFromString(json['authorType'] as String?);
  return authorType == PostAuthorType.plant
      ? SocialGenerationSource.legacy
      : SocialGenerationSource.user;
}

SocialGenerationSource _postGenerationSourceFromJson(
  Map<String, dynamic> json,
) {
  final raw = json['generationSource'] as String?;
  if (raw != null && raw.isNotEmpty) {
    return generationSourceFromString(raw);
  }
  final authorType = _authorTypeFromString(json['authorType'] as String?);
  return authorType == PostAuthorType.plant
      ? SocialGenerationSource.legacy
      : SocialGenerationSource.user;
}

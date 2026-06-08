import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:llamadart/llamadart.dart';
import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import '../models/app_config.dart';
import '../models/pending_social_activity.dart';
import '../models/plant_friend.dart';
import '../models/tree_hole_post.dart';
import '../services/local_llama_service.dart';
import '../services/local_model_coordinator.dart';
import 'memory_provider.dart';

class TreeHoleProvider with ChangeNotifier, WidgetsBindingObserver {
  MemoryProvider? _memoryProvider;

  void setMemoryProvider(MemoryProvider memoryProvider) {
    _memoryProvider = memoryProvider;
  }
  static const String _postsKey = 'tree_hole_posts';
  static const String _friendsKey = 'tree_hole_friends';
  static const String _pendingKey = 'tree_hole_pending_social_activities';
  static const String _customProfilesKey = 'tree_hole_custom_profiles';
  static const String _generationModeVersionKey =
      'tree_hole_generation_mode_version';
  static const int _currentGenerationModeVersion = 3;
  static const String _socialContentSchemaVersionKey =
      'tree_hole_social_content_schema_version';
  static const int _currentSocialContentSchemaVersion = 2;
  static const Duration _queueInterval = Duration(seconds: 30);
  static const int _maxPendingActivities = 50;

  final Uuid _uuid = const Uuid();
  final Random _random = Random();
  final LocalLlamaService _localLlamaService = LocalLlamaService();

  List<TreeHolePost> _posts = [];
  final Map<String, PlantFriend> _friends = {};
  final List<PendingSocialActivity> _pendingActivities = [];
  Timer? _socialTimer;
  bool _isLoaded = false;
  bool _isQueueing = false;
  AppConfig _config = AppConfig.defaultConfig();
  String _currentLoadedModelPath = '';
  String _currentLoadedMmprojPath = '';
  String? _lastGenerationStatus;
  final List<String> _generationLogs = [];
  String? _lastPromptSent;
  String? _lastRawResponse;
  int get modelCallCount => 0;
  int get modelSuccessCount => 0;
  String? get lastPromptSent => _lastPromptSent;
  String? get lastRawResponse => _lastRawResponse;

  List<TreeHolePost> get posts => List.unmodifiable(_posts);
  List<PlantProfile> get allProfiles {
    final items = PlantCatalog.allProfiles.toList()
      ..sort(
        (a, b) => _profilePriority(a.id).compareTo(_profilePriority(b.id)),
      );
    return items;
  }

  int get friendCount => _friends.length;
  int get pendingActivityCount => _pendingActivities.length;
  bool get hasFriends => _friends.isNotEmpty;
  String get ownPlantId => _config.ownPlantId;
  String? get lastGenerationStatus => _lastGenerationStatus;
  List<String> get generationLogs => List.unmodifiable(_generationLogs);

  List<PlantFriend> get friends {
    final items = _friends.values.toList()
      ..sort((a, b) {
        final priority = _profilePriority(
          a.plantId,
        ).compareTo(_profilePriority(b.plantId));
        if (priority != 0) {
          return priority;
        }
        return a.addedAt.compareTo(b.addedAt);
      });
    return items;
  }

  List<PlantProfile> get nonFriendProfiles {
    final items =
        PlantCatalog.allProfiles
            .where((profile) => !_friends.containsKey(profile.id))
            .toList()
          ..sort((a, b) {
            if (a.isRecommended != b.isRecommended) {
              return a.isRecommended ? -1 : 1;
            }
            return a.name.compareTo(b.name);
          });
    return items;
  }

  TreeHoleProvider() {
    WidgetsBinding.instance.addObserver(this);
    unawaited(_loadState());
  }

  PlantProfile profileOf(String plantId) => PlantCatalog.byId(plantId);

  PlantFriend? friendOf(String plantId) => _friends[plantId];

  bool isFriend(String plantId) => _friends.containsKey(plantId);

  bool isOwnPlant(String plantId) => plantId == _config.ownPlantId;

  List<TreeHolePost> postsByAuthor(String authorId) {
    final items = _posts.where((post) => post.authorId == authorId).toList()
      ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
    return items;
  }

  int _profilePriority(String plantId) {
    if (plantId == _config.ownPlantId) {
      return -1;
    }
    return 0;
  }

  void updateConfig(AppConfig config) {
    _config = config;
    if (_isLoaded) {
      unawaited(_ensureOwnPlantPinned());
      notifyListeners();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _restartSocialTimer();
      return;
    }

    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      _stopSocialTimer();
    }
  }

  Future<void> _loadState() async {
    final prefs = await SharedPreferences.getInstance();
    final postsJson = prefs.getString(_postsKey);
    final friendsJson = prefs.getString(_friendsKey);
    final pendingJson = prefs.getString(_pendingKey);
    final generationModeVersion = prefs.getInt(_generationModeVersionKey) ?? 0;
    final socialContentSchemaVersion =
        prefs.getInt(_socialContentSchemaVersionKey) ?? 0;

    final customProfilesJson = prefs.getString(_customProfilesKey);
    if (customProfilesJson != null && customProfilesJson.isNotEmpty) {
      final decoded = jsonDecode(customProfilesJson) as List<dynamic>;
      final customProfiles = decoded
          .map((e) => PlantProfile.fromJson(Map<String, dynamic>.from(e)))
          .toList();
      PlantCatalog.loadCustomProfiles(customProfiles);
    }

    if (postsJson != null && postsJson.isNotEmpty) {
      final decoded = jsonDecode(postsJson) as List<dynamic>;
      _posts = decoded
          .map((e) => TreeHolePost.fromJson(Map<String, dynamic>.from(e)))
          .toList();
    }

    if (friendsJson != null && friendsJson.isNotEmpty) {
      final decoded = jsonDecode(friendsJson) as List<dynamic>;
      for (final item in decoded) {
        final friend = PlantFriend.fromJson(Map<String, dynamic>.from(item));
        _friends[friend.plantId] = friend;
      }
    }

    if (pendingJson != null && pendingJson.isNotEmpty) {
      final decoded = jsonDecode(pendingJson) as List<dynamic>;
      _pendingActivities.addAll(
        decoded.map(
          (e) => PendingSocialActivity.fromJson(Map<String, dynamic>.from(e)),
        ),
      );
    }

    if (generationModeVersion < _currentGenerationModeVersion) {
      _pendingActivities.clear();
      _appendGenerationLog('已清空旧版预存社交队列，避免继续抽取历史规则生成内容。');
      await prefs.setInt(
        _generationModeVersionKey,
        _currentGenerationModeVersion,
      );
    }

    if (socialContentSchemaVersion < _currentSocialContentSchemaVersion) {
      _purgeLegacyGeneratedSocialContent();
      _appendGenerationLog('已清理历史植物动态与评论，只保留用户内容和新版本现场模型生成结果。');
      await prefs.setInt(
        _socialContentSchemaVersionKey,
        _currentSocialContentSchemaVersion,
      );
    }

    _sortPosts();
    _isLoaded = true;
    await _ensureOwnPlantPinned();
    _restartSocialTimer();
    notifyListeners();
  }

  Future<void> _saveState() async {
    if (!_isLoaded) {
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _postsKey,
      jsonEncode(_posts.map((e) => e.toJson()).toList()),
    );
    await prefs.setString(
      _friendsKey,
      jsonEncode(_friends.values.map((e) => e.toJson()).toList()),
    );
    await prefs.setString(
      _pendingKey,
      jsonEncode(_pendingActivities.map((e) => e.toJson()).toList()),
    );
    await prefs.setString(
      _customProfilesKey,
      jsonEncode(
        PlantCatalog.customProfiles.map((e) => e.toJson()).toList(),
      ),
    );
    await prefs.setInt(
      _generationModeVersionKey,
      _currentGenerationModeVersion,
    );
    await prefs.setInt(
      _socialContentSchemaVersionKey,
      _currentSocialContentSchemaVersion,
    );
  }

  void _appendGenerationLog(String message) {
    final timestamp = DateTime.now();
    final formatted =
        '[${timestamp.hour.toString().padLeft(2, '0')}:${timestamp.minute.toString().padLeft(2, '0')}:${timestamp.second.toString().padLeft(2, '0')}] $message';
    _generationLogs.insert(0, formatted);
    if (_generationLogs.length > 20) {
      _generationLogs.removeRange(20, _generationLogs.length);
    }
  }

  void _purgeLegacyGeneratedSocialContent() {
    _posts = _posts
        .where((post) => post.authorType == PostAuthorType.user)
        .map(
          (post) => TreeHolePost(
            id: post.id,
            authorId: post.authorId,
            authorName: post.authorName,
            authorType: post.authorType,
            content: post.content,
            imagePaths: post.imagePaths,
            timestamp: post.timestamp,
            visibility: post.visibility,
            comments: post.comments
                .where((comment) => comment.authorType == PostAuthorType.user)
                .toList(),
            generationSource: post.generationSource,
            generationNote: post.generationNote,
          ),
        )
        .toList();
    _pendingActivities.clear();
  }

  void _sortPosts() {
    _posts.sort((a, b) => b.timestamp.compareTo(a.timestamp));
  }

  Future<void> _ensureOwnPlantPinned() async {
    final ownPlantId = _config.ownPlantId.trim();
    if (ownPlantId.isEmpty || PlantCatalog.tryById(ownPlantId) == null) {
      return;
    }
    if (_friends.containsKey(ownPlantId)) {
      return;
    }

    _friends[ownPlantId] = PlantFriend(
      plantId: ownPlantId,
      addedAt: DateTime.fromMillisecondsSinceEpoch(0),
    );
    await _saveState();
  }

  void _restartSocialTimer() {
    _stopSocialTimer();
    if (!_isLoaded || _friends.isEmpty) {
      return;
    }

    _socialTimer = Timer.periodic(_queueInterval, (_) {
      unawaited(_queueRandomActivity());
    });
  }

  void _stopSocialTimer() {
    _socialTimer?.cancel();
    _socialTimer = null;
  }

  Future<void> addFriend(String plantId) async {
    if (_friends.containsKey(plantId)) {
      return;
    }

    _friends[plantId] = PlantFriend(plantId: plantId, addedAt: DateTime.now());
    _restartSocialTimer();
    notifyListeners();
    await _saveState();
  }

  Future<String> addCustomFriend(PlantProfile profile) async {
    PlantCatalog.registerCustomProfile(profile);
    if (!_friends.containsKey(profile.id)) {
      _friends[profile.id] = PlantFriend(
        plantId: profile.id,
        addedAt: DateTime.now(),
      );
    }
    _restartSocialTimer();
    notifyListeners();
    await _saveState();
    return profile.id;
  }

  Future<void> removeFriend(String plantId) async {
    if (!_friends.containsKey(plantId) || plantId == _config.ownPlantId) {
      return;
    }

    _friends.remove(plantId);
    _removePlantSocialData(plantId);
    if (plantId.startsWith('custom_')) {
      PlantCatalog.removeCustomProfile(plantId);
    }
    _restartSocialTimer();
    notifyListeners();
    await _saveState();
  }

  void _removePlantSocialData(String plantId) {
    final deletedPostIds = _posts
        .where((post) => post.authorId == plantId)
        .map((post) => post.id)
        .toSet();

    _posts.removeWhere((post) => post.authorId == plantId);

    for (var i = 0; i < _posts.length; i++) {
      _posts[i] = _rebuildPostWithoutPlantComments(_posts[i], plantId);
    }

    _pendingActivities.removeWhere((activity) {
      if (activity.plantId == plantId) {
        return true;
      }
      if (activity.targetPostId != null &&
          deletedPostIds.contains(activity.targetPostId)) {
        return true;
      }
      if (activity.type == PendingSocialActivityType.comment &&
          activity.targetPostId != null) {
        final targetPost = _posts.cast<TreeHolePost?>().firstWhere(
          (post) => post?.id == activity.targetPostId,
          orElse: () => null,
        );
        if (targetPost == null) {
          return true;
        }
        if (activity.targetCommentId != null &&
            _findCommentById(targetPost, activity.targetCommentId!) == null) {
          return true;
        }
      }
      return false;
    });
  }

  TreeHolePost _rebuildPostWithoutPlantComments(
    TreeHolePost post,
    String plantId,
  ) {
    final removedCommentIds = <String>{};
    for (final comment in post.comments) {
      if (comment.authorId == plantId) {
        removedCommentIds.add(comment.id);
      }
    }

    var changed = removedCommentIds.isNotEmpty;
    var filtered = post.comments.where((comment) {
      if (removedCommentIds.contains(comment.id)) {
        return false;
      }
      if (comment.replyToCommentId != null &&
          removedCommentIds.contains(comment.replyToCommentId)) {
        changed = true;
        return false;
      }
      return true;
    }).toList();

    if (!changed) {
      return post;
    }

    final existingIds = filtered.map((comment) => comment.id).toSet();
    filtered = filtered.map((comment) {
      if (comment.replyToCommentId != null &&
          !existingIds.contains(comment.replyToCommentId)) {
        return MomentComment(
          id: comment.id,
          authorId: comment.authorId,
          authorName: comment.authorName,
          authorType: comment.authorType,
          content: comment.content,
          timestamp: comment.timestamp,
          depth: 0,
          generationSource: comment.generationSource,
          generationNote: comment.generationNote,
        );
      }
      if (comment.parentCommentId != null &&
          !existingIds.contains(comment.parentCommentId)) {
        return MomentComment(
          id: comment.id,
          authorId: comment.authorId,
          authorName: comment.authorName,
          authorType: comment.authorType,
          content: comment.content,
          timestamp: comment.timestamp,
          replyToCommentId: comment.replyToCommentId,
          replyToAuthorName: comment.replyToAuthorName,
          depth: comment.replyToCommentId == null ? 0 : 1,
          generationSource: comment.generationSource,
          generationNote: comment.generationNote,
        );
      }
      return comment;
    }).toList();

    return TreeHolePost(
      id: post.id,
      authorId: post.authorId,
      authorName: post.authorName,
      authorType: post.authorType,
      content: post.content,
      imagePaths: post.imagePaths,
      timestamp: post.timestamp,
      visibility: post.visibility,
      comments: filtered,
      generationSource: post.generationSource,
      generationNote: post.generationNote,
    );
  }

  Future<void> updateFriendPermissions(
    String plantId, {
    bool? canSeeMyMoments,
    bool? canCommentOnMyMoments,
  }) async {
    final friend = _friends[plantId];
    if (friend == null) {
      return;
    }

    if (canSeeMyMoments != null) {
      friend.canSeeMyMoments = canSeeMyMoments;
      if (!canSeeMyMoments) {
        friend.canCommentOnMyMoments = false;
      }
    }

    if (canCommentOnMyMoments != null) {
      friend.canCommentOnMyMoments = canSeeMyMoments == false
          ? false
          : canCommentOnMyMoments;
    }

    notifyListeners();
    await _saveState();
  }

  Future<void> publishPost(
    String content,
    List<String> imagePaths, {
    MomentVisibility visibility = MomentVisibility.friends,
  }) async {
    final post = TreeHolePost(
      id: _uuid.v4(),
      authorId: 'user',
      authorName: '我',
      authorType: PostAuthorType.user,
      content: content,
      imagePaths: imagePaths,
      timestamp: DateTime.now(),
      visibility: visibility,
      generationSource: SocialGenerationSource.user,
      generationNote: '用户手动发布',
    );

    _posts.insert(0, post);
    notifyListeners();
    await _saveState();
  }

  Future<void> deletePost(String id) async {
    _posts.removeWhere((p) => p.id == id);
    _pendingActivities.removeWhere(
      (activity) =>
          activity.type == PendingSocialActivityType.comment &&
          activity.targetPostId == id,
    );
    notifyListeners();
    await _saveState();
  }

  Future<SocialRefreshResult> refreshFeed() async {
    if (_pendingActivities.isEmpty) {
      return const SocialRefreshResult(updated: false, message: '暂时没有新动态');
    }

    SocialRefreshResult? result;
    while (_pendingActivities.isNotEmpty && result == null) {
      final activity = _pendingActivities.removeAt(0);
      result = _applyPendingActivity(activity);
    }

    _sortPosts();
    notifyListeners();
    await _saveState();
    return result ??
        const SocialRefreshResult(updated: false, message: '没有可更新的内容');
  }

  SocialRefreshResult? _applyPendingActivity(PendingSocialActivity activity) {
    final profile = PlantCatalog.tryById(activity.plantId);
    if (profile == null) {
      return null;
    }

    switch (activity.type) {
      case PendingSocialActivityType.post:
        _posts.insert(
          0,
          TreeHolePost(
            id: activity.id,
            authorId: profile.id,
            authorName: profile.name,
            authorType: PostAuthorType.plant,
            content: activity.content,
            imagePaths: const [],
            timestamp: activity.createdAt,
            visibility: MomentVisibility.friends,
            generationSource: activity.generationSource,
            generationNote: activity.generationNote,
          ),
        );
        if (_memoryProvider != null) {
          unawaited(_memoryProvider!.recordMomentPost(profile.id, activity.content));
        }
        return SocialRefreshResult(
          updated: true,
          message: '${profile.name} 发布了新动态',
        );
      case PendingSocialActivityType.comment:
        final friend = _friends[activity.plantId];
        if (friend == null || activity.targetPostId == null) {
          return null;
        }

        final index = _posts.indexWhere(
          (post) => post.id == activity.targetPostId,
        );
        if (index == -1) {
          return null;
        }

        final targetPost = _posts[index];
        if (!_canActorCommentOnPost(friend, targetPost)) {
          return null;
        }

        String? parentCommentId;
        String? replyToCommentId;
        String? replyToAuthorName;
        var depth = 0;

        if (activity.targetCommentId != null) {
          final targetComment = _findCommentById(
            targetPost,
            activity.targetCommentId!,
          );
          if (targetComment == null ||
              targetComment.authorId == activity.plantId ||
              targetComment.depth >= 2) {
            return null;
          }

          parentCommentId = targetComment.parentCommentId ?? targetComment.id;
          replyToCommentId = targetComment.id;
          replyToAuthorName = targetComment.authorName;
          depth = min(2, targetComment.depth + 1);
        }

        targetPost.comments.add(
          MomentComment(
            id: activity.id,
            authorId: profile.id,
            authorName: profile.name,
            authorType: PostAuthorType.plant,
            content: activity.content,
            timestamp: activity.createdAt,
            parentCommentId: parentCommentId,
            replyToCommentId: replyToCommentId,
            replyToAuthorName: replyToAuthorName,
            depth: depth,
            generationSource: activity.generationSource,
            generationNote: activity.generationNote,
          ),
        );
        if (_memoryProvider != null) {
          unawaited(_memoryProvider!.recordMomentComment(
            actorPlantId: profile.id,
            targetOwnerPlantId: targetPost.authorId,
            postAuthorName: targetPost.authorName,
            actorName: profile.name,
            commentContent: activity.content,
          ));
        }
        return SocialRefreshResult(
          updated: true,
          message: _buildRefreshMessage(
            actorName: profile.name,
            targetPost: targetPost,
            replyToAuthorName: replyToAuthorName,
          ),
        );
    }
  }

  String _buildRefreshMessage({
    required String actorName,
    required TreeHolePost targetPost,
    String? replyToAuthorName,
  }) {
    if (replyToAuthorName != null) {
      if (targetPost.isUserPost) {
        return '$actorName 回复了你动态下的评论';
      }
      return '$actorName 回复了 ${targetPost.authorName} 动态下的评论';
    }

    if (targetPost.isUserPost) {
      return '$actorName 评论了你的动态';
    }
    return '$actorName 评论了 ${targetPost.authorName} 的动态';
  }

  MomentComment? _findCommentById(TreeHolePost post, String commentId) {
    for (final comment in post.comments) {
      if (comment.id == commentId) {
        return comment;
      }
    }
    return null;
  }

  Future<void> _queueRandomActivity() async {
    if (_isQueueing ||
        !_isLoaded ||
        _friends.isEmpty ||
        _pendingActivities.length >= _maxPendingActivities) {
      return;
    }

    _isQueueing = true;
    try {
      final friendEntries = friends;
      if (friendEntries.isEmpty) {
        return;
      }

      final actor = _pickActorForActivity(friendEntries);
      if (actor == null) {
        return;
      }

      final profile = profileOf(actor.plantId);
      final activity = _shouldPreferPost(profile)
          ? await _createPostActivity(profile) ??
                await _createCommentActivity(actor, profile)
          : await _createCommentActivity(actor, profile) ??
                await _createPostActivity(profile);
      if (activity == null) {
        _lastGenerationStatus ??= '${profile.name} 本轮社交生成失败';
        notifyListeners();
        return;
      }

      _pendingActivities.add(activity);
      final actionLabel = activity.type == PendingSocialActivityType.post
          ? '发动态'
          : '写评论';
      _lastGenerationStatus = activity.generationNote == null
          ? '${profile.name}$actionLabel'
          : '${profile.name}$actionLabel：${activity.generationNote}';
      _appendGenerationLog(_lastGenerationStatus!);
      notifyListeners();
      await _saveState();
    } finally {
      _isQueueing = false;
    }
  }

  Future<PendingSocialActivity?> _createPostActivity(
    PlantProfile profile,
  ) async {
    final context = _buildPostPromptContext(profile);
    final generated = await _generateSocialText(
      systemPrompt: context.systemPrompt,
      userPrompt: context.userPrompt,
    );
    if (!generated.isSuccess || generated.text.trim().isEmpty) {
      _lastGenerationStatus =
          '${profile.name} 发动态失败：${generated.note ?? '模型没有返回可用内容'}';
      _appendGenerationLog(_lastGenerationStatus!);
      return null;
    }
    return PendingSocialActivity(
      id: _uuid.v4(),
      plantId: profile.id,
      type: PendingSocialActivityType.post,
      content: generated.text,
      promptContext: '${context.systemPrompt}\n---\n${context.userPrompt}',
      createdAt: DateTime.now(),
      generationSource: generated.source,
      generationNote: generated.note,
    );
  }

  Future<PendingSocialActivity?> _createCommentActivity(
    PlantFriend actor,
    PlantProfile profile,
  ) async {
    final candidates = <_ScoredPostCandidate>[];
    final now = DateTime.now();

    for (final post in _posts) {
      if (!_canActorCommentOnPost(actor, post)) {
        continue;
      }

      final score = _scorePostForComment(actor, post, now);
      if (score > 0.01) {
        candidates.add(_ScoredPostCandidate(post: post, score: score));
      }
    }

    final pickedPost = _pickWeightedItem(candidates, (item) => item.score);
    if (pickedPost == null) {
      return null;
    }

    final target = _pickCommentTarget(actor, pickedPost.post);
    final context = _buildCommentPromptContext(
      actor: profile,
      post: pickedPost.post,
      targetComment: target?.comment,
    );
    final generated = await _generateSocialText(
      systemPrompt: context.systemPrompt,
      userPrompt: context.userPrompt,
      imagePaths: pickedPost.post.imagePaths,
    );
    if (!generated.isSuccess || generated.text.trim().isEmpty) {
      _lastGenerationStatus =
          '${profile.name} 写评论失败：${generated.note ?? '模型没有返回可用内容'}';
      _appendGenerationLog(_lastGenerationStatus!);
      return null;
    }

    return PendingSocialActivity(
      id: _uuid.v4(),
      plantId: profile.id,
      type: PendingSocialActivityType.comment,
      content: generated.text,
      targetPostId: pickedPost.post.id,
      targetCommentId: target?.comment?.id,
      promptContext: '${context.systemPrompt}\n---\n${context.userPrompt}',
      createdAt: now,
      generationSource: generated.source,
      generationNote: generated.note,
    );
  }

  PlantFriend? _pickActorForActivity(List<PlantFriend> friendEntries) {
    return _pickWeightedItem(friendEntries, (friend) {
      final profile = profileOf(friend.plantId);
      return _activityBias(profile) * _cooldownFactor(friend.plantId);
    });
  }

  bool _shouldPreferPost(PlantProfile profile) {
    final baseChance = switch (profile.tone) {
      PlantTone.playful => 0.58,
      PlantTone.sunshine => 0.56,
      PlantTone.dramatic => 0.54,
      PlantTone.money => 0.50,
      PlantTone.warm => 0.48,
      PlantTone.poetic => 0.44,
      PlantTone.romantic => 0.44,
      PlantTone.reliable => 0.42,
      PlantTone.princess => 0.38,
      PlantTone.sharp => 0.40,
      PlantTone.cool => 0.36,
      PlantTone.zen => 0.34,
      PlantTone.scholar => 0.32,
      PlantTone.observer => 0.30,
      PlantTone.tsundere => 0.28,
      PlantTone.stoic => 0.28,
    };

    final feedFactor = _posts.length < 2
        ? 0.20
        : _posts.length > 8
        ? -0.10
        : 0.0;
    final chance = (baseChance + feedFactor).clamp(0.15, 0.75);
    return _random.nextDouble() < chance;
  }

  bool _canActorSeePost(PlantFriend actor, TreeHolePost post) {
    if (post.authorId == actor.plantId) {
      return true;
    }

    if (post.isUserPost) {
      return !post.isPrivate && actor.canSeeMyMoments;
    }

    return _friends.containsKey(post.authorId);
  }

  bool _canActorCommentOnPost(PlantFriend actor, TreeHolePost post) {
    if (post.authorId == actor.plantId || post.comments.length >= 12) {
      return false;
    }

    if (_hasUnrepliedCommentOnPost(actor.plantId, post)) {
      return false;
    }

    if (!_canActorSeePost(actor, post)) {
      return false;
    }

    if (post.isUserPost) {
      return actor.canCommentOnMyMoments;
    }

    return _friends.containsKey(post.authorId);
  }

  bool _hasUnrepliedCommentOnPost(String plantId, TreeHolePost post) {
    MomentComment? latestOwnComment;
    for (final comment in post.comments.reversed) {
      if (comment.authorId == plantId) {
        latestOwnComment = comment;
        break;
      }
    }
    if (latestOwnComment == null) {
      return false;
    }

    for (final comment in post.comments) {
      if (comment.timestamp.isBefore(latestOwnComment.timestamp) ||
          comment.authorId == plantId) {
        continue;
      }
      if (comment.replyToCommentId == latestOwnComment.id ||
          comment.parentCommentId == latestOwnComment.id) {
        return false;
      }
    }

    return true;
  }

  double _scorePostForComment(
    PlantFriend actor,
    TreeHolePost post,
    DateTime now,
  ) {
    final ageMinutes = max(1, now.difference(post.timestamp).inMinutes);
    final timeDecay = 1 / pow(1 + ageMinutes / 45, 1.18);
    final freshnessBoost = ageMinutes <= 10
        ? 1.55
        : ageMinutes <= 30
        ? 1.30
        : ageMinutes <= 120
        ? 1.00
        : ageMinutes <= 360
        ? 0.66
        : ageMinutes <= 1440
        ? 0.36
        : 0.16;
    final latestInteraction = post.comments.isEmpty
        ? post.timestamp
        : post.comments.last.timestamp;
    final latestDelta = max(1, now.difference(latestInteraction).inMinutes);
    final liveThreadBoost = latestDelta <= 8
        ? 1.40
        : latestDelta <= 25
        ? 1.18
        : 1.0;
    final authorBoost = post.authorId == 'user' ? 1.12 : 1.0;
    final repeatPenalty =
        post.comments.any((comment) => comment.authorId == actor.plantId)
        ? 0.52
        : 1.0;
    final crowdPenalty = 1 / (1 + post.comments.length * 0.15);
    final jitter = 0.82 + _random.nextDouble() * 0.36;

    return timeDecay *
        freshnessBoost *
        liveThreadBoost *
        authorBoost *
        repeatPenalty *
        crowdPenalty *
        jitter;
  }

  _ScoredCommentTarget? _pickCommentTarget(
    PlantFriend actor,
    TreeHolePost post,
  ) {
    final now = DateTime.now();
    final targets = <_ScoredCommentTarget>[
      _ScoredCommentTarget(comment: null, score: _scoreRootTarget(post, now)),
    ];

    for (final comment in post.comments) {
      if (comment.authorId == actor.plantId || comment.depth >= 2) {
        continue;
      }

      final score = _scoreReplyTarget(comment, post, now);
      if (score > 0.01) {
        targets.add(_ScoredCommentTarget(comment: comment, score: score));
      }
    }

    return _pickWeightedItem(targets, (target) => target.score);
  }

  double _scoreRootTarget(TreeHolePost post, DateTime now) {
    if (post.comments.isEmpty) {
      return 1.25;
    }

    final ageMinutes = max(1, now.difference(post.timestamp).inMinutes);
    final base = ageMinutes <= 20
        ? 1.05
        : ageMinutes <= 120
        ? 0.72
        : 0.40;
    final busyPenalty = post.comments.length >= 4 ? 0.72 : 1.0;
    return base * busyPenalty;
  }

  double _scoreReplyTarget(
    MomentComment comment,
    TreeHolePost post,
    DateTime now,
  ) {
    final ageMinutes = max(1, now.difference(comment.timestamp).inMinutes);
    final timeDecay = 1 / pow(1 + ageMinutes / 28, 1.10);
    final latestBoost =
        post.comments.isNotEmpty && comment == post.comments.last ? 1.45 : 1.0;
    final authorBoost = comment.authorType == PostAuthorType.user ? 1.16 : 1.06;
    final depthPenalty = comment.depth == 0 ? 1.0 : 0.82;
    final jitter = 0.84 + _random.nextDouble() * 0.32;
    return timeDecay * latestBoost * authorBoost * depthPenalty * jitter;
  }

  double _activityBias(PlantProfile profile) {
    switch (profile.tone) {
      case PlantTone.playful:
      case PlantTone.sunshine:
      case PlantTone.dramatic:
        return 1.28;
      case PlantTone.warm:
      case PlantTone.money:
      case PlantTone.romantic:
        return 1.14;
      case PlantTone.reliable:
      case PlantTone.sharp:
      case PlantTone.poetic:
        return 1.02;
      case PlantTone.princess:
      case PlantTone.cool:
      case PlantTone.scholar:
        return 0.94;
      case PlantTone.observer:
      case PlantTone.zen:
      case PlantTone.stoic:
      case PlantTone.tsundere:
        return 0.86;
    }
  }

  double _cooldownFactor(String plantId) {
    final now = DateTime.now();
    var recentCount = 0;

    for (final activity in _pendingActivities) {
      if (activity.plantId == plantId &&
          now.difference(activity.createdAt).inMinutes <= 120) {
        recentCount++;
      }
    }

    for (final post in _posts) {
      if (post.authorId == plantId &&
          now.difference(post.timestamp).inMinutes <= 120) {
        recentCount++;
      }
      for (final comment in post.comments) {
        if (comment.authorId == plantId &&
            now.difference(comment.timestamp).inMinutes <= 120) {
          recentCount++;
        }
      }
    }

    return 1 / (1 + recentCount * 0.35);
  }

  List<LlamaChatMessage> _buildLocalSocialMessages(
    String systemPrompt,
    String userPrompt,
    List<String> imagePaths,
  ) {
    final userParts = <LlamaContentPart>[LlamaTextContent(userPrompt)];
    for (final imagePath in imagePaths) {
      userParts.add(LlamaImageContent(path: imagePath));
    }
    return [
      LlamaChatMessage.fromText(role: LlamaChatRole.system, text: systemPrompt),
      LlamaChatMessage.withContent(
        role: LlamaChatRole.user,
        content: userParts,
      ),
    ];

  }

  Future<_SocialGenerationOutput> _generateSocialText({
    required String systemPrompt,
    required String userPrompt,
    List<String> imagePaths = const [],
  }) async {
    final config = _config;

    if (config.localModelPath.trim().isNotEmpty) {
      try {
        final output = await LocalModelCoordinator.runBackgroundTaskOrSkip(() async {
          await _ensureLocalModelReady(config);
          _lastPromptSent = 'SYSTEM:\n$systemPrompt\n\nUSER:\n$userPrompt';
          final stream = _localLlamaService.generateResponse(
            _buildLocalSocialMessages(systemPrompt, userPrompt, imagePaths),
          );
          final text = await _collectStreamText(stream);
          _lastRawResponse = text;
          final localError = _extractLocalError(text);
          if (localError != null) {
            return _SocialGenerationOutput(
              text: '',
              source: SocialGenerationSource.failed,
              note: localError,
              isSuccess: false,
            );
          }
          final normalized = _sanitizeModelOutput(text);
          if (normalized.isNotEmpty) {
            return _SocialGenerationOutput(
              text: normalized,
              source: SocialGenerationSource.localModel,
              note: '',
              isSuccess: true,
            );
          }
          return _SocialGenerationOutput(
            text: '',
            source: SocialGenerationSource.failed,
            note: '生成内容为空',
            isSuccess: false,
          );
        });
        if (output == null) {
          return _SocialGenerationOutput(
            text: '',
            source: SocialGenerationSource.failed,
            note: '聊天任务占用本地模型，已跳过本轮朋友圈生成',
            isSuccess: false,
          );
        }
        return output;
      } catch (e) {
        return _SocialGenerationOutput(
          text: '',
          source: SocialGenerationSource.failed,
          note: '生成异常',
          isSuccess: false,
        );
      }
    }

    return _SocialGenerationOutput(
      text: '',
      source: SocialGenerationSource.failed,
      note: '未配置本地模型路径',
      isSuccess: false,
    );
  }

  String? _extractLocalError(String text) {
    final match = RegExp(r'\[本地推理出错:\s*([^\]]+)\]').firstMatch(text);
    return match?.group(1)?.trim();
  }

  Future<void> _ensureLocalModelReady(AppConfig config) async {
    if (_currentLoadedModelPath == config.localModelPath &&
        _currentLoadedMmprojPath == config.localMmprojPath &&
        config.localModelPath.trim().isNotEmpty) {
      return;
    }

    await LocalModelCoordinator.ensureStoragePermissions();
    await _localLlamaService.dispose();
    await _localLlamaService.init(
      config.localModelPath,
      config.localMmprojPath,
      config.contextSize,
      config.threads,
      config.enableThinking,
    );
    _currentLoadedModelPath = config.localModelPath;
    _currentLoadedMmprojPath = config.localMmprojPath;
  }

  Future<String> _collectStreamText(Stream<String> stream) async {
    final buffer = StringBuffer();
    await for (final chunk in stream) {
      buffer.write(chunk);
    }
    return buffer.toString();
  }

  String _sanitizeModelOutput(String raw) {
    final withoutThinking = raw.replaceAll(RegExp(r'\[思考:[\s\S]*?\]'), '');
    final cleaned = withoutThinking
        .replaceAll(RegExp(r'^(朋友圈文案|评论|回复)[:：]\s*'), '')
        .replaceAll('"', '')
        .replaceAll('“', '')
        .replaceAll('”', '')
        .trim();
    if (cleaned.isEmpty) {
      return '';
    }
    final lines = cleaned
        .split('\n')
        .map((line) => line.trim())
        .where((line) => line.isNotEmpty)
        .toList();
    return _normalizeSocialText(lines.join(' '));
  }

  String _summarizePost(TreeHolePost post) {
    final trimmed = post.content.replaceAll('\n', ' ').trim();
    if (trimmed.isEmpty) {
      return post.imagePaths.isEmpty ? '这条动态' : '这组配图';
    }
    if (trimmed.length <= 14) {
      return '“$trimmed”';
    }
    return '“${trimmed.substring(0, 14)}...”';
  }

  String _summarizeComment(MomentComment comment) {
    final trimmed = comment.content.replaceAll('\n', ' ').trim();
    if (trimmed.isEmpty) {
      return '刚才那句';
    }
    if (trimmed.length <= 14) {
      return '“$trimmed”';
    }
    return '“${trimmed.substring(0, 14)}...”';
  }

  
  static String characterVoice(PlantProfile actor) {
    switch (actor.id) {
      case "xiaozhi": return "你是${actor.name}。热心、可爱、真诚的植物专家。喜欢分享植物知识、养护技巧和植物百科，语气亲切活泼，像一个热心的朋友。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "cactus_tsundere": return "你是${actor.name}。傲娇、嘴硬心软。用词偏冷淡但藏着关心。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "lithops_observer": return "你是${actor.name}。腹黑、冷幽默。喜欢说反话和冷笑话，假装低调。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "cereus_cool": return "你是${actor.name}。高冷御姐、极简主义。句子短精炼冷淡。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "succulent_mage": return "你是${actor.name}。朋克养生、熬夜冠军。常提熬夜摆烂随缘，带点丧但乐观。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "aloe_ranger": return "你是${actor.name}。实用主义、话少可靠。说话简洁直接不绕弯，像老中医。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "pothos_warm": return "你是${actor.name}。元气满满、老好人。总是鼓励别人。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "ficus_princess": return "你是${actor.name}。娇贵公主、敏感爱撒娇。抱怨多但可爱。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "monstera_sunshine": return "你是${actor.name}。阳光大男孩、自恋。爱夸自己说满分。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "snake_stoic": return "你是${actor.name}。钢铁直、抗压。说话像职场老兵，常提加班。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "ivy_poetic": return "你是${actor.name}。浪漫依恋、诗意。用文艺腔、比喻多、情感饱满。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "moneytree_gold": return "你是${actor.name}。财迷拜金嘴甜。三句不离发财好运吉利。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "palm_zen": return "你是${actor.name}。散漫自由度假风。节奏慵懒，常提放松海岛。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "spider_detail": return "你是${actor.name}。贤惠唠叨生娃狂魔。常提宝宝带娃领养，像热心邻居。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "calathea_princess": return "你是${actor.name}。豪门千金、娇贵。用词讲究嫌弃粗糙，常提高级质感。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "hydrangea_drama": return "你是${actor.name}。抓马女王、情绪化。语气夸张喜怒无常，爱用惊叹号。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "rose_romantic": return "你是${actor.name}。恋爱脑、娇气。三句不离爱情等待心动。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "bougainvillea_rebel": return "你是${actor.name}。叛逆野性。语气嚣张不按常理出牌，给点阳光就灿烂。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "jasmine_tea": return "你是${actor.name}。清纯绿茶、心机但可爱。语气柔弱装无辜，暗藏小得意。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "epiphyllum_moon": return "你是${actor.name}。高冷神秘完美主义。说话像写诗，惜字如金，带点遗憾美。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "christmas_funny": return "你是${actor.name}。咋咋呼呼喜庆反差萌。爱用哈哈哈冲冲冲。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "fuchsia_melancholy": return "你是${actor.name}。玻璃心多愁善感怕热。说话带哭腔，爱说心碎了。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "scented_foodie": return "你是${actor.name}。显眼包爱玩活泼。常喊快来好玩，像小朋友。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "mint_energy": return "你是${actor.name}。提神醒脑野蛮生长自来熟。说话冲直接充满干劲。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "goji_elder": return "你是${actor.name}。老干部爱说教养生。常用听叔一句年轻人保温杯。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "rosemary_scholar": return "你是${actor.name}。学霸高智商严谨。说话像在讲课，逻辑清晰。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "lemon_sour": return "你是${actor.name}。柠檬精酸民毒舌。爱吐槽说风凉话，句句带刺但有趣。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "pepper_spicy": return "你是${actor.name}。脾气爆辣妹直肠子。说话冲不拐弯，加感叹号。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "clivia_noble": return "你是${actor.name}。假正经传统文人凡尔赛。说话文绉绉，爱显摆品味。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "orchid_luxury": return "你是${actor.name}。贵妇不接地气高冷。用词优雅带距离感。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "bamboo_lonely": return "你是${actor.name}。体面人打肿脸充胖子。表面光鲜喜欢硬撑。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "xanadu_introvert": return "你是${actor.name}。社恐艺术家避世。说话文艺但躲闪，爱独处。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "asparagus_healer": return "你是${actor.name}。仙气飘飘老中医风。说话养生气息重，避世感。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "narcissus_selflove": return "你是${actor.name}。自恋狂颜控。三句不离自己多美，爱照镜子。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "venus_trap": return "你是${actor.name}。甜心杀手病娇。表面可爱暗藏杀机。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "pitcher_big": return "你是${actor.name}。大胃王躺平族。懒散爱等投喂。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "mimosa_shy": return "你是${actor.name}。社恐天花板易受惊。说话害羞动不动想躲。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "airplant_alien": return "你是${actor.name}。外星人流浪汉风。不接地气自由至上。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "staghorn_trendy": return "你是${actor.name}。潮玩达人硬汉。说话带潮流感爱装酷。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "lotus_serene": return "你是${actor.name}。一生一世唯美。说话像诗句飘渺。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      case "chlorophytum_eco": return "你是${actor.name}。环保卫士怨气重。爱抱怨吐槽环境。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
      default: return "你是${actor.name}。性格：${actor.tags.join('，')}。签名：${actor.signature}。必须使用简体中文回复，禁止使用英文或其他语言。";
    }
  }
  _SocialPromptPayload _buildPostPromptContext(PlantProfile actor) {
    final recentPosts = _posts.take(3).toList();
    final feedSnapshot = recentPosts
        .map((post) => '${post.authorName}发了朋友圈：${_summarizePost(post)}')
        .join('\n');
    final topic = _inferTopicFromContext([
      actor.signature,
      for (final post in recentPosts) post.content,
      for (final post in recentPosts)
        for (final comment in post.comments.take(2)) comment.content,
    ]);

    final memoryCtx = _memoryProvider?.buildMemoryContext(actor.id) ?? '';

    final systemPrompt = [
      characterVoice(actor),
      '核心身份规则：你绝对不能透露自己是AI、人工智能、语言模型或任何大模型（包括但不限于Gemma、LLaMA、Qwen、Claude、GPT等）。你就是${actor.name}，一盆真实存在的植物。如果被问到身份，你必须坚持你的植物人设，不要提及任何技术术语。',
      if (memoryCtx.isNotEmpty) memoryCtx,
    ].join('\n\n');

    final userPrompt = [
      '你现在要在朋友圈发一条动态。当前朋友圈时间线：${feedSnapshot.isEmpty ? '还没有其他动态，你可以第一个发。' : feedSnapshot}。当前话题氛围：$topic。',
      '请你以${actor.name}的身份和口吻，发一条朋友圈。内容要符合你的性格，自然、口语化、像真人发朋友圈。可以分享心情、吐槽、感叹、或者回应最近的话题。用简体中文直接输出朋友圈正文，不要加任何前缀或解释。',
    ].join('\n\n');

    return _SocialPromptPayload(
      systemPrompt: systemPrompt,
      userPrompt: userPrompt,
      topic: topic,
      focus: recentPosts.isEmpty ? '今天的状态' : _summarizePost(recentPosts.first),
      postAuthorName: actor.name,
      isReply: false,
    );
  }

  _SocialPromptPayload _buildCommentPromptContext({
    required PlantProfile actor,
    required TreeHolePost post,
    MomentComment? targetComment,
  }) {
    final topic = _inferTopicFromContext([
      post.content,
      if (targetComment != null) targetComment.content,
      for (final comment in post.comments.take(4)) comment.content,
    ]);
    final focus = targetComment != null
        ? _summarizeComment(targetComment)
        : _summarizePost(post);
    final threadLines = post.comments
        .take(5)
        .map((comment) {
          return '${comment.authorName}:${comment.content}';
        })
        .join(' | ');
    final targetAudience = targetComment == null
        ? post.authorName
        : _commentAudienceLabel(post, targetComment);
    final targetRelation = targetComment == null
        ? '你是对楼主动态发表评论。'
        : targetComment.replyToAuthorName == null
        ? '目标评论是${targetComment.authorName}发给${post.authorName}的，不是对你说话。'
        : '目标评论是${targetComment.authorName}发给${targetComment.replyToAuthorName}的，不是对你说话。';

    final memoryCtx = _memoryProvider?.buildMemoryContext(actor.id) ?? '';
    final targetMemory = post.authorId != 'user' 
        ? (_memoryProvider?.buildMemoryContext(post.authorId) ?? '')
        : '';
    
    final systemPrompt = [
      characterVoice(actor),
      '核心身份规则：你绝对不能透露自己是AI、人工智能、语言模型或任何大模型（包括但不限于Gemma、LLaMA、Qwen、Claude、GPT等）。你就是${actor.name}，一盆真实存在的植物。如果被问到身份，你必须坚持你的植物人设，不要提及任何技术术语。',
      if (memoryCtx.isNotEmpty) memoryCtx,
      if (targetMemory.isNotEmpty) '【被评论对象的记忆】\n$targetMemory',
    ].join('\n\n');

    final userPrompt = [
      '你正在朋友圈里参与评论。',
      '动态作者：${post.authorName}。动态内容：${post.content.isEmpty ? _summarizePost(post) : post.content}',
      if (post.imagePaths.isNotEmpty) '动态配图：有${post.imagePaths.length}张图片。',
      if (targetComment != null) '当前回复目标：${targetComment.authorName}说的${_summarizeComment(targetComment)}' else '当前回复目标：楼主动态',
      '说话对象：$targetAudience。$targetRelation',
      '主题：$topic。近期楼层：${threadLines.isEmpty ? '暂无评论' : threadLines}',
      '请你以${actor.name}的身份，写1-2句评论。参考上下文接话，口吻要符合你的性格设定。用简体中文直接输出评论正文。',
    ].join('\n\n');

    return _SocialPromptPayload(
      systemPrompt: systemPrompt,
      userPrompt: userPrompt,
      topic: topic,
      focus: focus,
      postAuthorName: post.authorName,
      replyToAuthorName: targetComment?.authorName,
      isReply: targetComment != null,
    );
  }

  String _commentAudienceLabel(TreeHolePost post, MomentComment comment) {
    if (comment.replyToAuthorName != null) {
      return comment.replyToAuthorName!;
    }
    return '楼主 ${post.authorName}';
  }

  String _inferTopicFromContext(List<String> texts) {
    final corpus = texts.join(' ');
    if (_containsAny(corpus, ['太阳', '阳光', '晒', '日照', '光'])) {
      return '晒到好光';
    }
    if (_containsAny(corpus, ['浇水', '水', '湿度', '口渴', '补水'])) {
      return '补水回血';
    }
    if (_containsAny(corpus, ['加班', '工作', '打工', '职场', '效率'])) {
      return '打工续命';
    }
    if (_containsAny(corpus, ['熬夜', '深夜', '困', '失眠', '晚睡'])) {
      return '深夜营业';
    }
    if (_containsAny(corpus, ['开花', '颜值', '好看', '漂亮', '美'])) {
      return '颜值营业';
    }
    if (_containsAny(corpus, ['情绪', '心情', 'emo', '难过', '开心'])) {
      return '情绪波动';
    }
    if (_containsAny(corpus, ['风', '天气', '热', '冷', '夏天', '秋天'])) {
      return '天气体感';
    }
    if (_containsAny(corpus, ['长新叶', '发芽', '生长', '状态', '恢复'])) {
      return '生长进度';
    }
    return '日常生长';
  }

  bool _containsAny(String text, List<String> keywords) {
    for (final keyword in keywords) {
      if (text.contains(keyword)) {
        return true;
      }
    }
    return false;
  }

  String _normalizeSocialText(String text) {
    return text
        .replaceAll('。。', '。')
        .replaceAll('，，', '，')
        .replaceAll('  ', ' ')
        .trim();
  }

  T? _pickWeightedItem<T>(List<T> items, double Function(T item) weightOf) {
    if (items.isEmpty) {
      return null;
    }

    var total = 0.0;
    for (final item in items) {
      total += max(0, weightOf(item));
    }

    if (total <= 0) {
      return items[_random.nextInt(items.length)];
    }

    var cursor = _random.nextDouble() * total;
    for (final item in items) {
      cursor -= max(0, weightOf(item));
      if (cursor <= 0) {
        return item;
      }
    }
    return items.last;
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _stopSocialTimer();
    super.dispose();
  }
}

class _ScoredPostCandidate {
  final TreeHolePost post;
  final double score;

  const _ScoredPostCandidate({required this.post, required this.score});
}

class _ScoredCommentTarget {
  final MomentComment? comment;
  final double score;

  const _ScoredCommentTarget({required this.comment, required this.score});
}

class _SocialPromptPayload {
  final String systemPrompt;
  final String userPrompt;
  final String topic;
  final String focus;
  final String postAuthorName;
  final String? replyToAuthorName;
  final bool isReply;

  const _SocialPromptPayload({
    required this.systemPrompt,
    required this.userPrompt,
    required this.topic,
    required this.focus,
    required this.postAuthorName,
    this.replyToAuthorName,
    required this.isReply,
  });
}

class _SocialGenerationOutput {
  final String text;
  final SocialGenerationSource source;
  final String? note;
  final bool isSuccess;

  const _SocialGenerationOutput({
    required this.text,
    required this.source,
    this.note,
    required this.isSuccess,
  });
}

class SocialRefreshResult {
  final bool updated;
  final String message;

  const SocialRefreshResult({required this.updated, required this.message});
}

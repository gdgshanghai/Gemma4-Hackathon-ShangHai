import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/plant_friend.dart';
import '../../providers/tree_hole_provider.dart';
import '../../providers/memory_provider.dart';
import '../../widgets/pixel_plant_avatar.dart';
import '../camera/spirit_camera_screen.dart';
import '../chat/chat_screen.dart';
import 'add_friends_screen.dart';
import 'author_moments_screen.dart';

class FriendsScreen extends StatefulWidget {
  const FriendsScreen({super.key});

  @override
  State<FriendsScreen> createState() => _FriendsScreenState();
}

class _FriendsScreenState extends State<FriendsScreen> {
  String? _expandedFriendId;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey.shade100,
      appBar: AppBar(
        title: const Text('植物好友'),
        backgroundColor: Colors.white,
        foregroundColor: Colors.black87,
        actions: [
          IconButton(
            icon: const Icon(Icons.auto_awesome),
            tooltip: '有灵相机',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const SpiritCameraScreen(),
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.person_add_alt_1),
            tooltip: '添加好友',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const AddFriendsScreen(),
                ),
              );
            },
          ),
        ],
      ),
      body: Consumer<TreeHoleProvider>(
        builder: (context, provider, child) {
          final friendEntries = provider.friends
              .where((friend) => !provider.isOwnPlant(friend.plantId))
              .toList();

          if (friendEntries.isEmpty) {
            return Center(
              child: FilledButton.tonalIcon(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const AddFriendsScreen(),
                    ),
                  );
                },
                icon: const Icon(Icons.person_add_alt_1),
                label: const Text('去添加好友'),
              ),
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: friendEntries.length,
            itemBuilder: (context, index) {
              final friend = friendEntries[index];
              final profile = provider.profileOf(friend.plantId);
              final isOwnPlant = provider.isOwnPlant(profile.id);
              final isExpanded = _expandedFriendId == friend.plantId;

              return Container(
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withAlpha(15),
                      blurRadius: isExpanded ? 8 : 4,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: Column(
                  children: [
                    ListTile(
                      shape: const RoundedRectangleBorder(
                        borderRadius: BorderRadius.vertical(
                          top: Radius.circular(12),
                        ),
                      ),
                      leading: PixelPlantAvatar(plantId: profile.id, size: 48),
                      title: Text(
                        profile.name,
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.black87,
                        ),
                      ),
                      subtitle: Text(
                        '已加入好友列表',
                        style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                      ),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          TextButton.icon(
                            onPressed: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (context) => ChatScreen(initialPlantId: profile.id),
                                ),
                              );
                            },
                            icon: const Icon(Icons.chat_bubble_outline, size: 16),
                            label: const Text('聊天'),
                          ),
                          Icon(
                            isExpanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
                            color: Colors.grey,
                          ),
                        ],
                      ),
                      onTap: () {
                        setState(() {
                          _expandedFriendId = isExpanded ? null : friend.plantId;
                        });
                      },
                    ),
                    if (isExpanded)
                      _buildExpandedDetails(
                        context,
                        provider,
                        friend,
                        profile,
                        isOwnPlant,
                      ),
                  ],
                ),
              );
            },
          );
        },
      ),
    );
  }

  Widget _buildExpandedDetails(
    BuildContext context,
    TreeHoleProvider provider,
    PlantFriend friend,
    PlantProfile profile,
    bool isOwnPlant,
  ) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(12)),
      ),
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Divider(color: Colors.grey.shade300),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: profile.tags
                .map(
                  (tag) => Chip(
                    label: Text(tag, style: const TextStyle(fontSize: 12, color: Colors.black87)),
                    visualDensity: VisualDensity.compact,
                    backgroundColor: Colors.green.shade50,
                    side: BorderSide(color: Colors.green.shade200),
                  ),
                )
                .toList(),
          ),
          const SizedBox(height: 10),
          Text(
            profile.signature,
            style: TextStyle(
              color: Colors.grey.shade800,
              height: 1.5,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              FilledButton.tonal(
                onPressed: () async {
                  if (!isOwnPlant) {
                    await provider.removeFriend(profile.id);
                  }
                },
                child: Text(isOwnPlant ? '已置顶' : '删除好友'),
              ),
              const SizedBox(width: 12),
              Text(
                isOwnPlant ? '这是你的主植物，会始终置顶显示' : '已加入好友列表',
                style: TextStyle(color: Colors.grey.shade600),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => AuthorMomentsScreen(
                        authorId: profile.id,
                        authorName: profile.name,
                        isUser: false,
                      ),
                    ),
                  );
                },
                icon: const Icon(Icons.history),
                label: const Text('看朋友圈'),
              ),
              OutlinedButton.icon(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) =>
                          ChatScreen(initialPlantId: profile.id),
                    ),
                  );
                },
                icon: const Icon(Icons.chat_bubble_outline),
                label: const Text('聊天'),
              ),
              OutlinedButton.icon(
                onPressed: () async {
                  final memoryProvider =
                      Provider.of<MemoryProvider>(
                    context,
                    listen: false,
                  );
                  final hasMemory =
                      memoryProvider.hasMemory(profile.id);
                  if (!hasMemory) {
                    if (!context.mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          '${profile.name} 暂无记忆',
                        ),
                      ),
                    );
                    return;
                  }
                  final confirmed =
                      await showDialog<bool>(
                    context: context,
                    builder: (ctx) => AlertDialog(
                      title: const Text('清除记忆'),
                      content: Text(
                        '确定要清除 ${profile.name} 的所有记忆吗？清除后无法恢复。',
                      ),
                      actions: [
                        TextButton(
                          onPressed: () =>
                              Navigator.pop(ctx, false),
                          child: const Text('取消'),
                        ),
                        TextButton(
                          onPressed: () =>
                              Navigator.pop(ctx, true),
                          child: const Text('清除'),
                        ),
                      ],
                    ),
                  );
                  if (confirmed != true) return;
                  await memoryProvider.clearMemory(profile.id);
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        '已清除 ${profile.name} 的记忆',
                      ),
                    ),
                  );
                },
                icon: const Icon(Icons.delete_sweep),
                label: const Text('清除记忆'),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _PermissionTile(
            title: '允许它看我的朋友圈',
            subtitle: '关闭后它不会刷到你的公开动态，也不会评论你',
            value: friend.canSeeMyMoments,
            onChanged: (value) async {
              await provider.updateFriendPermissions(
                profile.id,
                canSeeMyMoments: value,
              );
            },
          ),
          _PermissionTile(
            title: '允许它评论我的朋友圈',
            subtitle: '关闭后它仍会发自己的朋友圈，但不会评论你',
            value: friend.canCommentOnMyMoments,
            onChanged: friend.canSeeMyMoments
                ? (value) async {
                    await provider.updateFriendPermissions(
                      profile.id,
                      canCommentOnMyMoments: value,
                    );
                  }
                : null,
          ),
        ],
      ),
    );
  }
}

class _PermissionTile extends StatelessWidget {
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool>? onChanged;

  const _PermissionTile({
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
      ),
      margin: const EdgeInsets.only(top: 8),
      child: SwitchListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 12),
        title: Text(title, style: const TextStyle(fontSize: 14)),
        subtitle: Text(subtitle, style: const TextStyle(fontSize: 12)),
        value: value,
        onChanged: onChanged,
      ),
    );
  }
}

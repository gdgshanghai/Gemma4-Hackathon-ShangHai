import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/tree_hole_provider.dart';
import '../../widgets/pixel_plant_avatar.dart';
import 'author_moments_screen.dart';
import 'publish_tree_hole_screen.dart';

class TreeHoleScreen extends StatelessWidget {
  const TreeHoleScreen({super.key});

  String _formatDate(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')} '
        '${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
  }

  Future<void> _refreshAndNotify(
    BuildContext context,
    TreeHoleProvider provider,
  ) async {
    final result = await provider.refreshFeed();
    if (!context.mounted) {
      return;
    }
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(result.message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('植物朋友圈'),
        actions: [
          Consumer<TreeHoleProvider>(
            builder: (context, provider, child) {
              return IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: () async {
                  await _refreshAndNotify(context, provider);
                },
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.camera_alt),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const PublishTreeHoleScreen(),
                ),
              );
            },
          ),
        ],
      ),
      body: Consumer<TreeHoleProvider>(
        builder: (context, provider, child) {
          return RefreshIndicator(
            onRefresh: () => _refreshAndNotify(context, provider),
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
              itemCount: provider.posts.isEmpty ? 1 : provider.posts.length,
              itemBuilder: (context, index) {
                if (provider.posts.isEmpty) {
                  return const _EmptyMomentsView();
                }

                final post = provider.posts[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  elevation: 0,
                  color: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(color: Colors.grey.shade200),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                              child: InkWell(
                                borderRadius: BorderRadius.circular(10),
                                onTap: () {
                                  Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (context) => AuthorMomentsScreen(
                                        authorId: post.authorId,
                                        authorName: post.authorName,
                                        isUser: post.isUserPost,
                                      ),
                                    ),
                                  );
                                },
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    PixelPlantAvatar(
                                      isUser: post.isUserPost,
                                      plantId: post.isUserPost
                                          ? null
                                          : post.authorId,
                                      size: 46,
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            post.authorName,
                                            style: const TextStyle(
                                              fontWeight: FontWeight.bold,
                                              fontSize: 16,
                                            ),
                                          ),
                                          const SizedBox(height: 4),
                                          Row(
                                            children: [
                                              Text(
                                                _formatDate(post.timestamp),
                                                style: const TextStyle(
                                                  color: Colors.grey,
                                                  fontSize: 12,
                                                ),
                                              ),
                                              const SizedBox(width: 8),
                                              Container(
                                                padding:
                                                    const EdgeInsets.symmetric(
                                                      horizontal: 8,
                                                      vertical: 2,
                                                    ),
                                                decoration: BoxDecoration(
                                                  color: post.isPrivate
                                                      ? Colors.orange.shade50
                                                      : Colors.green.shade50,
                                                  borderRadius:
                                                      BorderRadius.circular(
                                                        999,
                                                      ),
                                                ),
                                                child: Text(
                                                  post.isPrivate
                                                      ? '仅自己可见'
                                                      : '好友可见',
                                                  style: TextStyle(
                                                    fontSize: 11,
                                                    color: post.isPrivate
                                                        ? Colors.orange.shade800
                                                        : Colors.green.shade800,
                                                  ),
                                                ),
                                              ),
                                            ],
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            if (post.isUserPost)
                              IconButton(
                                icon: const Icon(
                                  Icons.delete_outline,
                                  color: Colors.grey,
                                  size: 20,
                                ),
                                onPressed: () {
                                  showDialog(
                                    context: context,
                                    builder: (ctx) => AlertDialog(
                                      title: const Text('删除朋友圈'),
                                      content: const Text('确定要删除这条记录吗？'),
                                      actions: [
                                        TextButton(
                                          onPressed: () => Navigator.pop(ctx),
                                          child: const Text('取消'),
                                        ),
                                        TextButton(
                                          onPressed: () {
                                            provider.deletePost(post.id);
                                            Navigator.pop(ctx);
                                          },
                                          child: const Text(
                                            '删除',
                                            style: TextStyle(color: Colors.red),
                                          ),
                                        ),
                                      ],
                                    ),
                                  );
                                },
                              ),
                          ],
                        ),
                        if (post.content.isNotEmpty) ...[
                          const SizedBox(height: 12),
                          Text(
                            post.content,
                            style: const TextStyle(fontSize: 15, height: 1.5),
                          ),
],
                        if (post.comments.isNotEmpty) ...[
                          const SizedBox(height: 14),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.grey.shade100,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: post.comments.map((comment) {
                                return Padding(
                                  padding: const EdgeInsets.only(bottom: 8),
                                  child: RichText(
                                    text: TextSpan(
                                      style: const TextStyle(
                                        color: Colors.black87,
                                        fontSize: 14,
                                        height: 1.4,
                                      ),
                                      children: [
                                        TextSpan(
                                          text: '${comment.authorName}：',
                                          style: const TextStyle(
                                            fontWeight: FontWeight.bold,
                                            color: Color(0xFF2C5EAA),
                                          ),
                                        ),
                                        if (comment.replyToAuthorName != null)
                                          TextSpan(
                                            text:
                                                '回复 ${comment.replyToAuthorName} ',
                                            style: const TextStyle(
                                              color: Color(0xFF6B7280),
                                            ),
                                          ),
                                        TextSpan(text: comment.content),
                                      ],
                                    ),
                                  ),
                                );
                              }).toList(),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }

}

class _EmptyMomentsView extends StatelessWidget {
  const _EmptyMomentsView();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(28),
      margin: const EdgeInsets.only(top: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: const Column(
        children: [
          Icon(Icons.spa_outlined, size: 40, color: Colors.green),
          SizedBox(height: 10),
          Text('还没有朋友圈内容'),
          SizedBox(height: 6),
          Text(
            '添加植物好友后，它们会开始分享日常',
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

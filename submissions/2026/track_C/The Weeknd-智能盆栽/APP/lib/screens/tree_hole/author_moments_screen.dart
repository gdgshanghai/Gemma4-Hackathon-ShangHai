import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/tree_hole_provider.dart';
import '../../widgets/pixel_plant_avatar.dart';

class AuthorMomentsScreen extends StatelessWidget {
  final String authorId;
  final String authorName;
  final bool isUser;

  const AuthorMomentsScreen({
    super.key,
    required this.authorId,
    required this.authorName,
    required this.isUser,
  });

  String _formatDate(DateTime date) {
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')} '
        '${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(isUser ? '我的朋友圈' : '$authorName 的朋友圈')),
      body: Consumer<TreeHoleProvider>(
        builder: (context, provider, child) {
          final posts = provider.postsByAuthor(authorId);
          if (posts.isEmpty) {
            return Center(
              child: Text(isUser ? '你还没有发过朋友圈' : '$authorName 还没有发过朋友圈'),
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: posts.length,
            itemBuilder: (context, index) {
              final post = posts[index];
              return Card(
                margin: const EdgeInsets.only(bottom: 12),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          PixelPlantAvatar(
                            isUser: isUser,
                            plantId: isUser ? null : authorId,
                            size: 42,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  authorName,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 16,
                                  ),
                                ),
                                Text(
                                  _formatDate(post.timestamp),
                                  style: const TextStyle(
                                    color: Colors.grey,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            ),
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
                      if (post.imagePaths.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: post.imagePaths.map((path) {
                            return ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: Image.file(
                                File(path),
                                width: 88,
                                height: 88,
                                fit: BoxFit.cover,
                              ),
                            );
                          }).toList(),
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
                              final prefix = comment.replyToAuthorName == null
                                  ? '${comment.authorName}：'
                                  : '${comment.authorName} 回复 ${comment.replyToAuthorName}：';
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
                                        text: prefix,
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          color: Color(0xFF2C5EAA),
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
          );
        },
      ),
    );
  }
}

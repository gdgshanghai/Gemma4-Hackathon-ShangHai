import 'dart:io';
import 'package:flutter/material.dart';
import '../models/message.dart';
import 'pixel_plant_avatar.dart';

class ChatBubble extends StatelessWidget {
  final Message message;
  final String? plantId;

  const ChatBubble({super.key, required this.message, this.plantId});

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 12.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser) ...[
            PixelPlantAvatar(plantId: plantId, size: 36),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(12.0),
              decoration: BoxDecoration(
                color: isUser ? const Color(0xFFE3F2FD) : Colors.white,
                border: Border.all(
                  color: isUser ? const Color(0xFFBBDEFB) : Colors.grey.shade200,
                ),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16.0),
                  topRight: const Radius.circular(16.0),
                  bottomLeft: Radius.circular(isUser ? 16.0 : 4.0),
                  bottomRight: Radius.circular(isUser ? 4.0 : 16.0),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.03),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (message.imagePaths.isNotEmpty) ...[
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children:
                          message.imagePaths.map((path) {
                            return ClipRRect(
                              borderRadius: BorderRadius.circular(10),
                              child: Image.file(
                                File(path),
                                width: 140,
                                height: 140,
                                fit: BoxFit.cover,
                              ),
                            );
                          }).toList(),
                    ),
                    if (message.content.trim().isNotEmpty)
                      const SizedBox(height: 8),
                  ],
                  if (message.content.trim().isNotEmpty)
                    Text(
                      message.content,
                      style: TextStyle(
                        color: isUser ? Colors.blue.shade900 : Colors.black87,
                        fontSize: 15,
                        height: 1.4,
                      ),
                    ),
                ],
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 8),
            const PixelPlantAvatar(isUser: true, size: 36),
          ],
        ],
      ),
    );
  }
}


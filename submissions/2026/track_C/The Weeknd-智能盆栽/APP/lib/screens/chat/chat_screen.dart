import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../../providers/chat_provider.dart';
import '../../providers/config_provider.dart';
import '../../providers/tree_hole_provider.dart';
import '../../widgets/chat_bubble.dart';

class ChatScreen extends StatefulWidget {
  final String? initialPlantId;

  const ChatScreen({super.key, this.initialPlantId});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final ImagePicker _picker = ImagePicker();
  final List<String> _pendingImagePaths = [];
  bool _startupGreetingRequested = false;

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _handleSubmitted(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty && _pendingImagePaths.isEmpty) {
      return;
    }
    final images = List<String>.from(_pendingImagePaths);
    _textController.clear();
    setState(() {
      _pendingImagePaths.clear();
    });
    final config = Provider.of<ConfigProvider>(context, listen: false).config;
    await Provider.of<ChatProvider>(
      context,
      listen: false,
    ).sendMessage(trimmed, config, imagePaths: images);
    _scrollToBottom();
  }

  Future<void> _pickImages() async {
    final images = await _picker.pickMultiImage();
    if (images.isEmpty || !mounted) {
      return;
    }
    setState(() {
      _pendingImagePaths.addAll(images.map((item) => item.path));
    });
  }

  void _removePendingImage(int index) {
    setState(() {
      _pendingImagePaths.removeAt(index);
    });
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      if (widget.initialPlantId != null) {
        Provider.of<ChatProvider>(
          context,
          listen: false,
        ).setActiveConversation(widget.initialPlantId!);
      }
    });
  }

  Future<void> _pickConversation() async {
    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    final treeHoleProvider = Provider.of<TreeHoleProvider>(
      context,
      listen: false,
    );
    final selected = await showModalBottomSheet<String>(
      context: context,
      builder: (context) {
        final friends = treeHoleProvider.friends
            .where((friend) => !treeHoleProvider.isOwnPlant(friend.plantId))
            .toList();
        return SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              const ListTile(
                title: Text(
                  '选择聊天对象',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
              ListTile(
                leading: const CircleAvatar(child: Icon(Icons.smart_toy)),
                title: Text(chatProvider.assistantDisplayName),
                selected:
                    chatProvider.activeConversationId ==
                    ChatProvider.assistantConversationId,
                onTap: () {
                  Navigator.pop(context, ChatProvider.assistantConversationId);
                },
              ),
              for (final friend in friends)
                ListTile(
                  leading: const CircleAvatar(child: Icon(Icons.spa)),
                  title: Text(treeHoleProvider.profileOf(friend.plantId).name),
                  subtitle: treeHoleProvider.isOwnPlant(friend.plantId)
                      ? const Text('我的植物')
                      : null,
                  selected: chatProvider.activeConversationId == friend.plantId,
                  onTap: () {
                    Navigator.pop(context, friend.plantId);
                  },
                ),
            ],
          ),
        );
      },
    );

    if (selected != null) {
      chatProvider.setActiveConversation(selected);
      _scrollToBottom();
    }
  }

  @override
  Widget build(BuildContext context) {
    final configProvider = context.watch<ConfigProvider>();
    if (!_startupGreetingRequested &&
        widget.initialPlantId == null &&
        !configProvider.isLoading) {
      _startupGreetingRequested = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) {
          return;
        }
        Provider.of<ChatProvider>(
          context,
          listen: false,
        ).prepareStartupAssistantGreeting(configProvider.config);
      });
    }

    return Scaffold(
      appBar: AppBar(
        title: Consumer<ChatProvider>(
          builder: (context, chatProvider, child) {
            final showDot = !chatProvider.isModelLoading;
            return Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (showDot)
                  Container(
                    width: 8,
                    height: 8,
                    margin: const EdgeInsets.only(right: 6),
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: Color(0xFF4CAF50),
                    ),
                  ),
                Flexible(
                  child: Text(
                    chatProvider.activeConversationTitle,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            );
          },
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.people_outline),
            onPressed: _pickConversation,
            tooltip: '选择好友聊天',
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            onPressed: () {
              Provider.of<ChatProvider>(context, listen: false).clearMessages();
            },
            tooltip: '清空对话',
          ),
        ],
      ),
      body: Column(
        children: [
          Consumer<ChatProvider>(
            builder: (context, chatProvider, child) {
              final errorLog = chatProvider.lastErrorLog;
              if (errorLog == null || errorLog.isEmpty) {
                return const SizedBox.shrink();
              }
              return Container(
                width: double.infinity,
                color: Colors.red.shade50,
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                child: Text(
                  errorLog,
                  style: TextStyle(color: Colors.red.shade800, fontSize: 12),
                ),
              );
            },
          ),
          Expanded(
            child: Consumer<ChatProvider>(
              builder: (context, chatProvider, child) {
                return ListView.builder(
                  controller: _scrollController,
                  itemCount: chatProvider.messages.length,
                  itemBuilder: (context, index) {
                    final message = chatProvider.messages[index];
                    return ChatBubble(
                      message: message,
                      plantId: chatProvider.activePlantId,
                    );
                  },
                );
              },
            ),
          ),
          const Divider(height: 1.0),
          Container(
            decoration: BoxDecoration(color: Theme.of(context).cardColor),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (_pendingImagePaths.isNotEmpty)
                  SizedBox(
                    height: 96,
                    child: ListView.builder(
                      padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
                      scrollDirection: Axis.horizontal,
                      itemCount: _pendingImagePaths.length,
                      itemBuilder: (context, index) {
                        final path = _pendingImagePaths[index];
                        return Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: Stack(
                            children: [
                              ClipRRect(
                                borderRadius: BorderRadius.circular(10),
                                child: Image.file(
                                  File(path),
                                  width: 80,
                                  height: 80,
                                  fit: BoxFit.cover,
                                ),
                              ),
                              Positioned(
                                top: 2,
                                right: 2,
                                child: GestureDetector(
                                  onTap: () => _removePendingImage(index),
                                  child: Container(
                                    decoration: const BoxDecoration(
                                      color: Colors.black54,
                                      shape: BoxShape.circle,
                                    ),
                                    child: const Icon(
                                      Icons.close,
                                      size: 18,
                                      color: Colors.white,
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                _buildTextComposer(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTextComposer() {
    return IconTheme(
      data: IconThemeData(color: Theme.of(context).colorScheme.secondary),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 8.0),
        child: Row(
          children: [
            IconButton(
              icon: const Icon(Icons.image_outlined),
              onPressed: _pickImages,
              tooltip: '发送图片',
            ),
            Flexible(
              child: TextField(
                controller: _textController,
                onSubmitted: _handleSubmitted,
                decoration: const InputDecoration.collapsed(
                  hintText: '发送消息给当前聊天对象...',
                ),
              ),
            ),
            Container(
              margin: const EdgeInsets.symmetric(horizontal: 4.0),
              child: IconButton(
                icon: const Icon(Icons.send),
                onPressed: () => _handleSubmitted(_textController.text),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

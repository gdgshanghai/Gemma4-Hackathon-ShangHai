import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:image_picker/image_picker.dart';
import '../../models/tree_hole_post.dart';
import '../../providers/tree_hole_provider.dart';

class PublishTreeHoleScreen extends StatefulWidget {
  const PublishTreeHoleScreen({super.key});

  @override
  State<PublishTreeHoleScreen> createState() => _PublishTreeHoleScreenState();
}

class _PublishTreeHoleScreenState extends State<PublishTreeHoleScreen> {
  final TextEditingController _contentController = TextEditingController();
  final List<String> _imagePaths = [];
  final ImagePicker _picker = ImagePicker();
  bool _isPublishing = false;
  MomentVisibility _visibility = MomentVisibility.friends;

  Future<void> _pickImages() async {
    final List<XFile> images = await _picker.pickMultiImage();
    if (images.isNotEmpty) {
      setState(() {
        _imagePaths.addAll(images.map((e) => e.path));
      });
    }
  }

  void _removeImage(int index) {
    setState(() {
      _imagePaths.removeAt(index);
    });
  }

  void _publish() async {
    if (_contentController.text.trim().isEmpty && _imagePaths.isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('不能发表空内容哦')));
      return;
    }

    setState(() {
      _isPublishing = true;
    });

    await Provider.of<TreeHoleProvider>(context, listen: false).publishPost(
      _contentController.text.trim(),
      _imagePaths,
      visibility: _visibility,
    );

    if (mounted) {
      Navigator.pop(context);
    }
  }

  @override
  void dispose() {
    _contentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('发表树洞'),
        actions: [
          TextButton(
            onPressed: _isPublishing ? null : _publish,
            child: const Text(
              '发表',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SegmentedButton<MomentVisibility>(
              showSelectedIcon: false,
              segments: const [
                ButtonSegment(
                  value: MomentVisibility.friends,
                  label: Text('好友可见'),
                  icon: Icon(Icons.people_outline),
                ),
                ButtonSegment(
                  value: MomentVisibility.private,
                  label: Text('仅自己可见'),
                  icon: Icon(Icons.lock_outline),
                ),
              ],
              selected: {_visibility},
              onSelectionChanged: (value) {
                setState(() {
                  _visibility = value.first;
                });
              },
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _contentController,
              maxLines: 8,
              minLines: 4,
              decoration: const InputDecoration(
                hintText: '分享这一刻的想法...',
                border: InputBorder.none,
              ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ..._imagePaths.asMap().entries.map((entry) {
                  final index = entry.key;
                  final path = entry.value;
                  return Stack(
                    children: [
                      Container(
                        width: 100,
                        height: 100,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(8),
                          image: DecorationImage(
                            image: FileImage(File(path)),
                            fit: BoxFit.cover,
                          ),
                        ),
                      ),
                      Positioned(
                        top: 0,
                        right: 0,
                        child: GestureDetector(
                          onTap: () => _removeImage(index),
                          child: Container(
                            decoration: const BoxDecoration(
                              color: Colors.black54,
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(
                              Icons.close,
                              color: Colors.white,
                              size: 20,
                            ),
                          ),
                        ),
                      ),
                    ],
                  );
                }),
                if (_imagePaths.length < 9)
                  GestureDetector(
                    onTap: _pickImages,
                    child: Container(
                      width: 100,
                      height: 100,
                      decoration: BoxDecoration(
                        color: Colors.grey[200],
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.add_a_photo,
                        size: 40,
                        color: Colors.grey,
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

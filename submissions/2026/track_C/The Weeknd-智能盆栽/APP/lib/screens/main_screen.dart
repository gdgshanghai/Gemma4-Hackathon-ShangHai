import 'package:flutter/material.dart';
import 'chat/chat_screen.dart';
import 'config/config_screen.dart';
import 'planter/planter_status_screen.dart';
import 'tree_hole/friends_screen.dart';
import 'tree_hole/tree_hole_screen.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _currentIndex = 0;

  final List<Widget> _pages = [
    const ChatScreen(),
    const FriendsScreen(),
    const TreeHoleScreen(),
    const PlanterStatusScreen(),
    const ConfigScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _pages[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        type: BottomNavigationBarType.fixed,
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.chat), label: '对话'),
          BottomNavigationBarItem(icon: Icon(Icons.people), label: '好友'),
          BottomNavigationBarItem(icon: Icon(Icons.park), label: '朋友圈'),
          BottomNavigationBarItem(
            icon: Icon(Icons.local_florist),
            label: '盆栽状态',
          ),
          BottomNavigationBarItem(icon: Icon(Icons.settings), label: '配置'),
        ],
      ),
    );
  }
}

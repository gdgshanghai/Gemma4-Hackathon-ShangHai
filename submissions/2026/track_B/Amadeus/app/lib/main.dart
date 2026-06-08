import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:flutter/services.dart';

import 'splash_screen.dart';

List<CameraDescription> cameras = []; // 全局变量，存储可用摄像头

Future<void> main() async {
  // 确保 Flutter 绑定已初始化
  WidgetsFlutterBinding.ensureInitialized();

  // 获取可用摄像头列表
  try {
    cameras = await availableCameras();
  } on MissingPluginException catch (e) {
    // Unsupported platforms can still use image picking.
    print('Camera plugin missing: $e');
    cameras = [];
  } on CameraException catch (e) {
    print('Camera error: ${e.code}\nError Message: ${e.description}');
    cameras = [];
  } catch (e) {
    print('Unexpected camera init error: $e');
    cameras = [];
  }

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: '陶瓷AI考古助手',
      theme: ThemeData(
        primarySwatch: Colors.brown,
        visualDensity: VisualDensity.adaptivePlatformDensity,
      ),
      home: SplashScreen(camera: cameras.isEmpty ? null : cameras.first),
    );
  }
}

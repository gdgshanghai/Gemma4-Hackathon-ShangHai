import 'dart:async';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'home_page.dart';

class SplashScreen extends StatefulWidget {
  final CameraDescription? camera;

  const SplashScreen({super.key, this.camera});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {
  late AnimationController _fadeController;
  late AnimationController _crackController;
  late Animation<double> _crackAnimation;

  @override
  void initState() {
    super.initState();

    // 控制整体淡入
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    );

    // 控制开片纹路生长
    _crackController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2500),
    );

    _crackAnimation = CurvedAnimation(
      parent: _crackController,
      curve: Curves.easeInOutQuart,
    );

    _startAnimation();
  }

  Future<void> _startAnimation() async {
    _fadeController.forward();
    await Future.delayed(const Duration(milliseconds: 400));
    _crackController.forward();

    // 动画结束后跳转到首页
    Timer(const Duration(milliseconds: 3500), () {
      if (mounted) {
        Navigator.of(context).pushReplacement(
          PageRouteBuilder(
            pageBuilder: (context, animation, secondaryAnimation) =>
                HomePage(camera: widget.camera),
            transitionsBuilder:
                (context, animation, secondaryAnimation, child) {
                  return FadeTransition(opacity: animation, child: child);
                },
            transitionDuration: const Duration(milliseconds: 800),
          ),
        );
      }
    });
  }

  @override
  void dispose() {
    _fadeController.dispose();
    _crackController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF2F4F46), // 图标同款深松绿
      body: FadeTransition(
        opacity: _fadeController,
        child: Stack(
          fit: StackFit.expand,
          children: [
            // 动态开片背景
            AnimatedBuilder(
              animation: _crackAnimation,
              builder: (context, child) {
                return CustomPaint(
                  painter: CrackleSplashPainter(
                    progress: _crackAnimation.value,
                  ),
                );
              },
            ),
            // 中心品牌 Logo
            Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    '瓷 语',
                    style: TextStyle(
                      color: Color(0xFFD4AF37), // 金色
                      fontSize: 42,
                      fontWeight: FontWeight.w200,
                      letterSpacing: 20,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'K I L N  E C H O',
                    style: TextStyle(
                      color: const Color(0xFFD4AF37).withOpacity(0.6),
                      fontSize: 10,
                      letterSpacing: 4,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 模拟哥窑“金丝铁线”的绘制器
class CrackleSplashPainter extends CustomPainter {
  final double progress;

  CrackleSplashPainter({required this.progress});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);

    // 绘制铁线 (Iron Wire) - 粗而深
    final ironPaint = Paint()
      ..color = Colors.black.withOpacity(0.3 * progress)
      ..strokeWidth = 4.0
      ..style = PaintingStyle.stroke;

    // 绘制金丝 (Gold Thread) - 细而密
    final goldPaint = Paint()
      ..color = const Color(0xB3D4AF37).withOpacity(0.4 * progress)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    // 模拟几条主要的“铁线”路径
    _drawCrack(canvas, size, ironPaint, [
      Offset(0, size.height * 0.3),
      Offset(size.width * 0.4, size.height * 0.5),
      Offset(size.width, size.height * 0.7),
    ]);

    _drawCrack(canvas, size, ironPaint, [
      Offset(size.width * 0.5, 0),
      Offset(size.width * 0.3, size.height * 0.6),
      Offset(size.width * 0.8, size.height),
    ]);

    // 绘制更密集的“金丝”
    if (progress > 0.5) {
      final goldProgress = (progress - 0.5) * 2;
      _drawCrack(canvas, size, goldPaint, [
        Offset(size.width * 0.2, size.height * 0.4),
        Offset(size.width * 0.35, size.height * 0.45),
      ]);
    }
  }

  void _drawCrack(Canvas canvas, Size size, Paint paint, List<Offset> points) {
    if (points.length < 2) return;
    final path = Path();
    path.moveTo(points[0].dx, points[0].dy);

    // 通过只在循环的特定步长中绘制，模拟“断裂”和“非连线”的效果
    for (var i = 1; i < points.length; i++) {
      if (i % 2 != 0) {
        path.quadraticBezierTo(
          points[i - 1].dx + 20,
          points[i - 1].dy + 20,
          points[i].dx,
          points[i].dy,
        );
      } else {
        path.moveTo(points[i].dx, points[i].dy);
      }
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CrackleSplashPainter oldDelegate) =>
      oldDelegate.progress != progress;
}

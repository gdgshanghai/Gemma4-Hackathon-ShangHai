import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/chat_provider.dart';
import 'providers/config_provider.dart';
import 'providers/memory_provider.dart';
import 'providers/tree_hole_provider.dart';
import 'services/quote_service.dart';
import 'screens/splash_screen.dart';

void main() {
  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => ConfigProvider()),
        ChangeNotifierProvider(create: (_) {
          final memoryProvider = MemoryProvider();
          memoryProvider.loadAllMemories();
          return memoryProvider;
        }),
        ChangeNotifierProxyProvider2<ConfigProvider, MemoryProvider, ChatProvider>(
          create: (_) => ChatProvider(),
          update: (_, configProvider, memoryProvider, chatProvider) {
            chatProvider ??= ChatProvider();
            chatProvider.setMemoryProvider(memoryProvider);
            chatProvider.updateConfig(configProvider.config);
            return chatProvider;
          },
        ),
        ChangeNotifierProxyProvider2<ConfigProvider, MemoryProvider, TreeHoleProvider>(
          create: (_) => TreeHoleProvider(),
          update: (_, configProvider, memoryProvider, treeHoleProvider) {
            treeHoleProvider ??= TreeHoleProvider();
            treeHoleProvider.updateConfig(configProvider.config);
            treeHoleProvider.setMemoryProvider(memoryProvider);
            return treeHoleProvider;
          },
        ),
      ],
      child: const AIChatApp(),
    ),
  );
}

class AIChatApp extends StatefulWidget {
  const AIChatApp({super.key});

  @override
  State<AIChatApp> createState() => _AIChatAppState();
}

class _AIChatAppState extends State<AIChatApp> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      unawaited(
        Future.delayed(const Duration(seconds: 12), () {
          _pushStartupQuote();
        }),
      );
    });
  }

  Future<void> _pushStartupQuote() async {
    if (!mounted) return;
    try {
      final config = context.read<ConfigProvider>().config;
      final memoryProvider = context.read<MemoryProvider>();
      final memoryContext = memoryProvider.buildMemoryContext(config.ownPlantId);
      final quoteService = QuoteService();
      unawaited(quoteService.generateAndPush(
        config: config,
        memoryContext: memoryContext,
      ));
    } catch (e) {
      debugPrint('启动语录推送失败: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Gemma 4 Smart Planter',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        visualDensity: VisualDensity.adaptivePlatformDensity,
        useMaterial3: true,
      ),
      home: const SplashScreen(),
    );
  }
}

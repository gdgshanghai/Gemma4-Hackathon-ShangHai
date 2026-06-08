import 'dart:async';
import 'package:permission_handler/permission_handler.dart';

class LocalModelCoordinator {
  static Future<void> _tail = Future.value();
  static Future<void>? _permissionRequestFuture;
  static int _chatTaskDepth = 0;

  static bool get isChatTaskRunning => _chatTaskDepth > 0;

  static Future<void> ensureStoragePermissions() {
    final current = _permissionRequestFuture;
    if (current != null) {
      return current;
    }

    final future = _requestStoragePermissions();
    _permissionRequestFuture = future.whenComplete(() {
      if (identical(_permissionRequestFuture, future)) {
        _permissionRequestFuture = null;
      }
    });
    return _permissionRequestFuture!;
  }

  static Future<T> runChatTask<T>(Future<T> Function() task) async {
    _chatTaskDepth++;
    try {
      return await runExclusive(task);
    } finally {
      _chatTaskDepth--;
    }
  }

  static Future<T?> runBackgroundTaskOrSkip<T>(Future<T> Function() task) async {
    if (isChatTaskRunning) {
      return null;
    }
    return runExclusive(task);
  }

  static Future<T> runExclusive<T>(Future<T> Function() task) {
    final completer = Completer<T>();
    final previous = _tail;

    _tail = completer.future.then<void>(
      (_) {},
      onError: (_, stackTrace) {},
    );

    unawaited(() async {
      try {
        await previous;
        completer.complete(await task());
      } catch (e, st) {
        completer.completeError(e, st);
      }
    }());

    return completer.future;
  }

  static Future<void> _requestStoragePermissions() async {
    await [Permission.storage, Permission.manageExternalStorage].request();
  }
}

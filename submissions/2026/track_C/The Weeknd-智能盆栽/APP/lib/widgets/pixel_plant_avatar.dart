import 'package:flutter/material.dart';
import '../models/plant_friend.dart';

class PixelPlantAvatar extends StatelessWidget {
  final String? plantId;
  final double size;
  final bool isUser;

  const PixelPlantAvatar({
    super.key,
    this.plantId,
    this.size = 44,
    this.isUser = false,
  });

  @override
  Widget build(BuildContext context) {
    if (isUser) {
      return _PixelBox(
        size: size,
        backgroundColor: const Color(0xFF5C8DFF),
        borderColor: const Color(0xFF26428B),
        child: Icon(
          Icons.face_4_rounded,
          size: size * 0.6,
          color: Colors.white,
        ),
      );
    }

    final profile = plantId != null ? PlantCatalog.tryById(plantId!) : null;
    final colors = _paletteForTone(profile?.tone ?? PlantTone.warm);

    return _PixelBox(
      size: size,
      backgroundColor: colors.$1,
      borderColor: colors.$2,
      child: Icon(
        _iconForKey(profile?.iconKey ?? 'leaf'),
        size: size * 0.56,
        color: colors.$3,
      ),
    );
  }

  (Color, Color, Color) _paletteForTone(PlantTone tone) {
    switch (tone) {
      case PlantTone.tsundere:
        return (
          const Color(0xFF7CCB5E),
          const Color(0xFF2C6A1B),
          const Color(0xFFF4FFF0),
        );
      case PlantTone.observer:
        return (
          const Color(0xFF8B8578),
          const Color(0xFF4B463E),
          const Color(0xFFFFF7E4),
        );
      case PlantTone.cool:
        return (
          const Color(0xFF7EC8B8),
          const Color(0xFF1A6B5A),
          const Color(0xFFF3FFFC),
        );
      case PlantTone.zen:
        return (
          const Color(0xFFB79864),
          const Color(0xFF71562F),
          const Color(0xFFFFF5E8),
        );
      case PlantTone.reliable:
        return (
          const Color(0xFF6AB17D),
          const Color(0xFF27563A),
          const Color(0xFFF4FFF6),
        );
      case PlantTone.warm:
        return (
          const Color(0xFF8BCF74),
          const Color(0xFF356A26),
          const Color(0xFFF5FFF2),
        );
      case PlantTone.princess:
        return (
          const Color(0xFFDA9CE7),
          const Color(0xFF81408B),
          const Color(0xFFFFF4FF),
        );
      case PlantTone.sunshine:
        return (
          const Color(0xFFF3B340),
          const Color(0xFF9A6300),
          const Color(0xFFFFF8E6),
        );
      case PlantTone.stoic:
        return (
          const Color(0xFF7BAF62),
          const Color(0xFF375E27),
          const Color(0xFFF6FFF1),
        );
      case PlantTone.poetic:
        return (
          const Color(0xFF7AA6E5),
          const Color(0xFF325488),
          const Color(0xFFF4F9FF),
        );
      case PlantTone.money:
        return (
          const Color(0xFFD5B347),
          const Color(0xFF80630A),
          const Color(0xFFFFF8E6),
        );
      case PlantTone.dramatic:
        return (
          const Color(0xFFE678A4),
          const Color(0xFF8E2850),
          const Color(0xFFFFF2F7),
        );
      case PlantTone.romantic:
        return (
          const Color(0xFFE88A94),
          const Color(0xFF943845),
          const Color(0xFFFFF3F5),
        );
      case PlantTone.playful:
        return (
          const Color(0xFF6FC5D9),
          const Color(0xFF1C6D7F),
          const Color(0xFFF0FDFF),
        );
      case PlantTone.scholar:
        return (
          const Color(0xFF9AA16A),
          const Color(0xFF525826),
          const Color(0xFFF9FBEA),
        );
      case PlantTone.sharp:
        return (
          const Color(0xFFE06D5D),
          const Color(0xFF7A241A),
          const Color(0xFFFFF2F0),
        );
    }
  }

  IconData _iconForKey(String iconKey) {
    switch (iconKey) {
      case 'cactus':
      case 'pillar':
      case 'aloe':
      case 'blade':
      case 'bamboo':
        return Icons.park_rounded;
      case 'stone':
        return Icons.hexagon_rounded;
      case 'succulent':
      case 'leaf_fan':
      case 'fern':
      case 'airplant':
        return Icons.spa_rounded;
      case 'vine':
      case 'ivy':
      case 'money':
      case 'eco':
        return Icons.eco_rounded;
      case 'ficus':
      case 'palm':
      case 'monstera':
      case 'calathea':
      case 'lotus':
        return Icons.local_florist_rounded;
      case 'hanger':
        return Icons.filter_vintage_rounded;
      case 'flower_ball':
      case 'rose':
      case 'jasmine':
      case 'moonflower':
      case 'bell_flower':
      case 'water_flower':
      case 'orchid':
      case 'clivia':
        return Icons.flare_rounded;
      case 'bougainvillea':
      case 'pepper':
        return Icons.whatshot_rounded;
      case 'festive':
        return Icons.celebration_rounded;
      case 'scent':
      case 'mint':
      case 'rosemary':
        return Icons.grass_rounded;
      case 'berry':
      case 'citrus':
        return Icons.circle_rounded;
      case 'trap':
      case 'pitcher':
        return Icons.pets_rounded;
      case 'mimosa':
        return Icons.waving_hand_rounded;
      case 'antler':
        return Icons.forest_rounded;
      default:
        return Icons.local_florist_rounded;
    }
  }
}

class _PixelBox extends StatelessWidget {
  final double size;
  final Color backgroundColor;
  final Color borderColor;
  final Widget child;

  const _PixelBox({
    required this.size,
    required this.backgroundColor,
    required this.borderColor,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      padding: EdgeInsets.all(size * 0.16),
      decoration: BoxDecoration(
        color: backgroundColor,
        border: Border.all(color: borderColor, width: 2),
        boxShadow: [
          BoxShadow(
            color: borderColor.withValues(alpha: 0.18),
            offset: const Offset(2, 2),
            blurRadius: 0,
          ),
        ],
      ),
      child: FittedBox(child: child),
    );
  }
}

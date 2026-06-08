class PlanterData {
  final double temperature;
  final int moisture;
  final int emotion;
  final bool isSleeping;
  final bool hasOverride;

  PlanterData({
    required this.temperature,
    required this.moisture,
    required this.emotion,
    required this.isSleeping,
    required this.hasOverride,
  });

  factory PlanterData.fromJson(Map<String, dynamic> json) {
    return PlanterData(
      temperature: (json['temperature'] ?? 0.0).toDouble(),
      moisture: (json['moisture'] ?? 0).toInt(),
      emotion: (json['emotion'] ?? 0).toInt(),
      isSleeping: json['is_sleeping'] ?? false,
      hasOverride: json['has_override'] ?? false,
    );
  }
}

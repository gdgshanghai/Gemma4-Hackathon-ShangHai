<?php

declare(strict_types=1);

final class FallDetectionService
{
    public function __construct(private readonly SystemStateService $stateService)
    {
    }

    /**
     * Reserved endpoint for AI team YOLO/OpenCV results.
     * Current owner scope: return mock/current JSON only.
     */
    public function current(): array
    {
        $state = $this->stateService->current();
        $vision = $state['vision'] ?? [];

        return [
            'fall_detected' => (bool) ($vision['fall_detected'] ?? false),
            'confidence' => (float) ($vision['confidence'] ?? 0),
            'fps' => (int) ($vision['fps'] ?? 0),
            'detections' => $vision['detections'] ?? [],
            'source' => $vision['mode'] ?? 'mock',
        ];
    }
}

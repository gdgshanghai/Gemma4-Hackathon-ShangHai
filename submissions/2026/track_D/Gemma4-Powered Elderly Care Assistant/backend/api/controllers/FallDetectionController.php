<?php

declare(strict_types=1);

final class FallDetectionController
{
    public function __construct(
        private readonly FallDetectionService $fallDetectionService,
        private readonly SystemStateService $stateService
    ) {
    }

    /**
     * GET /api/fall-detection
     * Return latest YOLO detection result and update dashboard state.
     */
    public function show(): void
    {
        $detection = $this->fallDetectionService->current();

        Response::json([
            'detection' => $detection,
            'state' => $this->stateService->current(),
        ]);
    }
}

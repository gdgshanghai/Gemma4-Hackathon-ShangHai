<?php

declare(strict_types=1);

final class VideoStreamController
{
    public function __construct(private readonly VideoStreamService $videoStreamService)
    {
    }

    /**
     * GET /api/video-stream
     * Return video stream configuration for camera/demo mode.
     */
    public function show(): void
    {
        $mode = (string) Request::query('mode', 'camera');
        Response::json(['video' => $this->videoStreamService->metadata($mode)]);
    }
}

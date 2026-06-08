<?php

declare(strict_types=1);

final class VideoStreamService
{
    public function __construct(private readonly array $config)
    {
    }

    /**
     * Return video stream metadata for frontend mode switching.
     */
    public function metadata(string $mode): array
    {
        return [
            'mode' => $mode,
            'transport' => 'frontend-camera-or-demo-video',
            'camera_stream_url' => $this->config['video']['camera_stream_url'],
            'demo_video_url' => $this->config['video']['demo_video_url'],
            'note' => 'OpenCV MJPEG streaming can replace this endpoint later.',
        ];
    }
}

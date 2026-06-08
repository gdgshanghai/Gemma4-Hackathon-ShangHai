<?php

declare(strict_types=1);

final class AppConfig
{
    /**
     * Centralized runtime configuration for PHP API.
     */
    public static function get(): array
    {
        return [
            'ai_backend_url' => 'http://127.0.0.1:8001',
            'api_token' => '',
            'fall_confidence_threshold' => 0.78,
            'emergency_countdown_seconds' => 10,
            'video' => [
                'camera_stream_url' => '/api/video-stream?mode=camera',
                'demo_video_url' => '/assets/videos/demo-fall.mp4',
            ],
        ];
    }
}

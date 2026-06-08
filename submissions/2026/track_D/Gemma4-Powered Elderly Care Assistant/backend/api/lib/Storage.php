<?php

declare(strict_types=1);

final class Storage
{
    public function __construct(private readonly string $storageDir)
    {
        if (!is_dir($this->storageDir)) {
            mkdir($this->storageDir, 0777, true);
        }
    }

    /**
     * Read current monitoring state from JSON storage.
     */
    public function readState(): array
    {
        $file = $this->statePath();
        if (!file_exists($file)) {
            $this->writeState($this->defaultState());
        }

        $content = file_get_contents($file);
        $state = json_decode($content ?: '', true);
        return is_array($state) ? $state : $this->defaultState();
    }

    /**
     * Persist current monitoring state.
     */
    public function writeState(array $state): void
    {
        $state['updated_at'] = date(DATE_ATOM);
        file_put_contents(
            $this->statePath(),
            json_encode($state, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT),
            LOCK_EX
        );
    }

    public function defaultState(): array
    {
        return [
            'vision' => [
                'fall_detected' => false,
                'confidence' => 0.05,
                'label' => '老人正常活动',
                'fps' => 0,
                'detections' => [],
                'mode' => 'camera',
            ],
            'speech' => [
                'transcript' => '',
                'intent' => 'none',
            ],
            'context' => [
                'no_response_seconds' => 0,
                'last_interaction_at' => null,
            ],
            'intervention' => [
                'active' => false,
                'voice_prompt' => '系统正在待命。',
            ],
            'decision' => [
                'risk_level' => 'low',
                'risk_score' => 12,
                'emergency_alert' => false,
                'action' => '持续监测',
                'reason' => '当前没有发现异常。',
                'reply_analysis' => 'No active voice check.',
            ],
            'emergency' => [
                'triggered' => false,
                'countdown_seconds' => 10,
                'contact_status' => '待命',
            ],
            'ai_backend' => [
                'last_update_at' => null,
                'source' => null,
                'pipeline_id' => null,
            ],
            'updated_at' => date(DATE_ATOM),
        ];
    }

    private function statePath(): string
    {
        return $this->storageDir . '/state.json';
    }
}

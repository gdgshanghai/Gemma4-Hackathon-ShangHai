<?php

declare(strict_types=1);

final class AiClient
{
    public function __construct(private readonly string $baseUrl)
    {
    }

    /**
     * Send multimodal state to Python AI backend for Gemma4 decision analysis.
     */
    public function analyze(array $state): array
    {
        $payload = json_encode(['state' => $state], JSON_UNESCAPED_UNICODE);
        $context = stream_context_create([
            'http' => [
                'method' => 'POST',
                'header' => "Content-Type: application/json\r\n",
                'content' => $payload,
                'timeout' => 3,
                'ignore_errors' => true,
            ],
        ]);

        $response = @file_get_contents($this->baseUrl . '/analyze', false, $context);
        if ($response === false) {
            throw new RuntimeException('AI backend is unavailable.');
        }

        $decoded = json_decode($response, true);
        if (!is_array($decoded)) {
            throw new RuntimeException('AI backend returned invalid JSON.');
        }

        return $decoded;
    }
}

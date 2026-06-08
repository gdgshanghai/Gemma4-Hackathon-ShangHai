<?php

declare(strict_types=1);

final class MockScenarioService
{
    private const ALLOWED = [
        'normal',
        'suspected_fall',
        'voice_checking',
        'responded_ok',
        'no_response',
        'emergency',
    ];

    public function __construct(private readonly string $mockDir)
    {
    }

    /**
     * Load a frontend demo scenario from mock JSON.
     */
    public function load(string $scenario): array
    {
        if (!in_array($scenario, self::ALLOWED, true)) {
            throw new InvalidArgumentException('Unknown mock scenario.');
        }

        $path = $this->mockDir . '/' . $scenario . '.json';
        $content = file_get_contents($path);
        $data = json_decode($content ?: '', true);

        if (!is_array($data)) {
            throw new RuntimeException('Invalid mock scenario JSON: ' . $scenario);
        }

        $data['updated_at'] = date(DATE_ATOM);
        return $data;
    }

    public function list(): array
    {
        return self::ALLOWED;
    }
}

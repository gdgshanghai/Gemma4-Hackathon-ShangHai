<?php

declare(strict_types=1);

final class AiUpdateService
{
    public function __construct(
        private readonly SystemStateService $stateService,
        private readonly Logger $logger
    ) {
    }

    /**
     * Receive JSON from Python AI backend and merge it into dashboard state.
     */
    public function ingest(array $payload): array
    {
        if (!isset($payload['vision']) && !isset($payload['speech']) && !isset($payload['decision'])) {
            throw new InvalidArgumentException('AI update must include vision, speech, or decision data.');
        }

        $state = $this->stateService->current();

        foreach (['vision', 'speech', 'context', 'intervention', 'decision', 'emergency'] as $section) {
            if (isset($payload[$section]) && is_array($payload[$section])) {
                if ($section === 'vision' || $section === 'speech' || $section === 'decision') {
                    $state[$section] = $payload[$section];
                    continue;
                }

                $state[$section] = array_replace_recursive($state[$section] ?? [], $payload[$section]);
            }
        }

        $state['ai_backend'] = [
            'last_update_at' => date(DATE_ATOM),
            'source' => $payload['source'] ?? 'python-ai-service',
            'pipeline_id' => $payload['pipeline_id'] ?? null,
        ];

        if (($state['decision']['emergency_alert'] ?? false) === true) {
            $state['emergency']['triggered'] = true;
            $state['emergency']['countdown_seconds'] = 0;
            $state['emergency']['contact_status'] = $state['emergency']['contact_status'] ?? 'Notifying family';
        }

        $saved = $this->stateService->save($state);
        $this->logger->info('AI update ingested from Python service.');
        return $saved;
    }
}

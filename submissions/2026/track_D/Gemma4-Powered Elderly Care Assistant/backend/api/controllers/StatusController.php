<?php

declare(strict_types=1);

final class StatusController
{
    public function __construct(
        private readonly SystemStateService $stateService,
        private readonly Logger $logger
    ) {
    }

    /**
     * GET /api/status
     * Return current monitoring state for frontend polling.
     */
    public function show(): void
    {
        Response::json(['state' => $this->stateService->current()]);
    }

    /**
     * POST /api/status/analyze
     * Ask Python AI backend to evaluate current multimodal state.
     */
    public function analyze(): void
    {
        $state = $this->stateService->current();
        $this->logger->info('Mock analysis requested. Returning current demo decision.');

        Response::json([
            'state' => $state,
            'ai_result' => [
                'mode' => 'mock',
                'decision' => $state['decision'] ?? [],
            ],
        ]);
    }
}

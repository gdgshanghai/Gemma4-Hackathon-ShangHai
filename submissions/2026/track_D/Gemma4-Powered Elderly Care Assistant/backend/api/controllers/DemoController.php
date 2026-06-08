<?php

declare(strict_types=1);

final class DemoController
{
    public function __construct(
        private readonly SystemStateService $stateService,
        private readonly MockScenarioService $mockScenarioService,
        private readonly Logger $logger
    ) {
    }

    /**
     * POST /api/demo
     * Apply a mock scenario for Hackathon presentation.
     */
    public function simulate(): void
    {
        try {
            $input = Request::json();
            $scenario = (string) ($input['scenario'] ?? 'normal');
            $state = $this->mockScenarioService->load($scenario);
            $state = $this->stateService->save($state);
            $this->logger->info('Mock scenario applied: ' . $scenario);

            Response::json([
                'scenario' => $scenario,
                'state' => $state,
            ], 'Mock scenario applied.');
        } catch (InvalidArgumentException $exception) {
            Response::error($exception->getMessage(), 422, [
                'available_scenarios' => $this->mockScenarioService->list(),
            ]);
        }
    }
}

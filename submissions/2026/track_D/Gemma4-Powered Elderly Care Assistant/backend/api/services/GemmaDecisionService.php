<?php

declare(strict_types=1);

final class GemmaDecisionService
{
    public function __construct(private readonly SystemStateService $stateService)
    {
    }

    /**
     * Reserved endpoint for Gemma4 AI reasoning.
     * Current owner scope: expose mock/current decision JSON only.
     */
    public function current(): array
    {
        $state = $this->stateService->current();
        return $state['decision'] ?? [];
    }

    public function state(): array
    {
        return $this->stateService->current();
    }
}

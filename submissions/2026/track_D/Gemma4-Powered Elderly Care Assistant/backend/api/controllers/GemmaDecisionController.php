<?php

declare(strict_types=1);

final class GemmaDecisionController
{
    public function __construct(private readonly GemmaDecisionService $decisionService)
    {
    }

    /**
     * GET /api/gemma-decision
     * Return Gemma4 multimodal reasoning result for current state.
     */
    public function show(): void
    {
        $state = $this->decisionService->state();
        Response::json([
            'decision' => $state['decision'],
            'state' => $state,
        ]);
    }
}

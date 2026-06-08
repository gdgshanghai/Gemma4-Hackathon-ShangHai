<?php

declare(strict_types=1);

final class EmergencyController
{
    public function __construct(private readonly EmergencyService $emergencyService)
    {
    }

    /**
     * POST /api/emergency
     * Trigger emergency alarm and family contact workflow.
     */
    public function trigger(): void
    {
        $state = $this->emergencyService->trigger(Request::json());
        Response::json(['state' => $state], 'Emergency alarm triggered.');
    }
}

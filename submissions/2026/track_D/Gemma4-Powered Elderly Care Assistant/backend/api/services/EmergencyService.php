<?php

declare(strict_types=1);

final class EmergencyService
{
    public function __construct(
        private readonly SystemStateService $stateService,
        private readonly Logger $logger
    ) {
    }

    /**
     * Trigger emergency rescue workflow.
     */
    public function trigger(array $payload): array
    {
        $state = $this->stateService->current();
        $state['decision'] = [
            'risk_level' => 'high',
            'risk_score' => 100,
            'emergency_alert' => true,
            'action' => '触发紧急报警',
            'reason' => $payload['reason'] ?? '手动或系统高风险规则触发紧急报警。',
            'model' => 'dashboard-emergency-service',
        ];
        $state['emergency'] = [
            'triggered' => true,
            'countdown_seconds' => 0,
            'contact_status' => '正在联系家属',
            'source' => $payload['source'] ?? 'system',
        ];

        $this->logger->error('Emergency triggered: ' . $state['decision']['reason']);
        return $this->stateService->save($state);
    }
}

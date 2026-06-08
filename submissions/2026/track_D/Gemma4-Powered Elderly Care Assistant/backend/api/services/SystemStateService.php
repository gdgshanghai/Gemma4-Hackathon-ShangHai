<?php

declare(strict_types=1);

final class SystemStateService
{
    public function __construct(private readonly Storage $storage)
    {
    }

    /**
     * Read current dashboard state.
     */
    public function current(): array
    {
        $state = $this->storage->readState();
        return $this->normalize($state);
    }

    /**
     * Persist normalized dashboard state.
     */
    public function save(array $state): array
    {
        $normalized = $this->normalize($state);
        $this->storage->writeState($normalized);
        return $normalized;
    }

    private function normalize(array $state): array
    {
        $defaults = $this->storage->defaultState();
        $state = array_replace_recursive($defaults, $state);

        $state['vision']['detections'] = $state['vision']['detections'] ?? [];
        $state['vision']['fps'] = $state['vision']['fps'] ?? 0;
        $state['emergency'] = $state['emergency'] ?? [
            'triggered' => false,
            'countdown_seconds' => 10,
            'contact_status' => '待命',
        ];

        return $state;
    }
}

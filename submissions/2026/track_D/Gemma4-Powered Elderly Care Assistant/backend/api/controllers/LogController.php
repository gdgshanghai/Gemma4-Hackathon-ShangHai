<?php

declare(strict_types=1);

final class LogController
{
    public function __construct(private readonly Logger $logger)
    {
    }

    /**
     * GET /api/logs
     * Return recent JSON log entries.
     */
    public function index(): void
    {
        Response::json(['logs' => $this->logger->recent()]);
    }
}

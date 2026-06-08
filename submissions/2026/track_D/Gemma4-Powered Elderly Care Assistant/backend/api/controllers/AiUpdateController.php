<?php

declare(strict_types=1);

final class AiUpdateController
{
    public function __construct(private readonly AiUpdateService $aiUpdateService)
    {
    }

    /**
     * POST /api/ai-update
     * Receive JSON output from Python YOLO/OpenCV/Whisper/Gemma4 pipeline.
     */
    public function store(): void
    {
        try {
            $state = $this->aiUpdateService->ingest(Request::json());
            Response::json(['state' => $state], 'AI update saved.');
        } catch (InvalidArgumentException $exception) {
            Response::error($exception->getMessage(), 422);
        }
    }
}

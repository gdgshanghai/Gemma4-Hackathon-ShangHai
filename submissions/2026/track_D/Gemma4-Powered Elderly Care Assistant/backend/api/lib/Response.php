<?php

declare(strict_types=1);

final class Response
{
    /**
     * Return a successful unified JSON response.
     */
    public static function json(array $data = [], string $message = 'OK', int $status = 200): void
    {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode([
            'success' => true,
            'message' => $message,
            'data' => $data,
            'timestamp' => date(DATE_ATOM),
        ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
        exit;
    }

    /**
     * Return an error using the same JSON response envelope.
     */
    public static function error(string $message, int $status = 400, array $data = []): void
    {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode([
            'success' => false,
            'message' => $message,
            'data' => $data,
            'timestamp' => date(DATE_ATOM),
        ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
        exit;
    }
}

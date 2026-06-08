<?php

declare(strict_types=1);

final class Request
{
    /**
     * Decode JSON body safely.
     */
    public static function json(): array
    {
        $raw = file_get_contents('php://input') ?: '{}';
        $data = json_decode($raw, true);
        return is_array($data) ? $data : [];
    }

    public static function query(string $key, mixed $default = null): mixed
    {
        return $_GET[$key] ?? $default;
    }
}

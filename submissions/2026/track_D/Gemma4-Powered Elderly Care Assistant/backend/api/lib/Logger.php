<?php

declare(strict_types=1);

final class Logger
{
    public function __construct(private readonly string $logFile)
    {
        $dir = dirname($this->logFile);
        if (!is_dir($dir)) {
            mkdir($dir, 0777, true);
        }
    }

    public function info(string $message): void
    {
        $this->write('INFO', $message);
    }

    public function warning(string $message): void
    {
        $this->write('WARNING', $message);
    }

    public function error(string $message): void
    {
        $this->write('ERROR', $message);
    }

    /**
     * Return recent logs for the frontend event panel.
     */
    public function recent(int $limit = 80): array
    {
        if (!file_exists($this->logFile)) {
            return [];
        }

        $lines = file($this->logFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [];
        $lines = array_slice($lines, -$limit);

        return array_values(array_filter(array_map(function (string $line): ?array {
            $entry = json_decode($line, true);
            return is_array($entry) ? $entry : null;
        }, $lines)));
    }

    private function write(string $level, string $message): void
    {
        $entry = [
            'created_at' => date(DATE_ATOM),
            'level' => $level,
            'message' => $message,
        ];
        file_put_contents(
            $this->logFile,
            json_encode($entry, JSON_UNESCAPED_UNICODE) . PHP_EOL,
            FILE_APPEND | LOCK_EX
        );
    }
}

<?php

declare(strict_types=1);

$requestPath = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) ?: '/';

if (strpos($requestPath, '/api') === 0) {
    require __DIR__ . '/backend/api/index.php';
    return true;
}

$publicPath = realpath(__DIR__ . '/frontend');
$filePath = realpath($publicPath . $requestPath);

if ($filePath !== false && strpos($filePath, $publicPath) === 0 && is_file($filePath)) {
    $extension = strtolower(pathinfo($filePath, PATHINFO_EXTENSION));
    $types = [
        'css' => 'text/css; charset=utf-8',
        'js' => 'application/javascript; charset=utf-8',
        'html' => 'text/html; charset=utf-8',
        'json' => 'application/json; charset=utf-8',
        'png' => 'image/png',
        'jpg' => 'image/jpeg',
        'jpeg' => 'image/jpeg',
        'svg' => 'image/svg+xml',
        'mp4' => 'video/mp4',
    ];
    header('Content-Type: ' . ($types[$extension] ?? 'application/octet-stream'));
    readfile($filePath);
    return true;
}

require $publicPath . '/index.html';
return true;

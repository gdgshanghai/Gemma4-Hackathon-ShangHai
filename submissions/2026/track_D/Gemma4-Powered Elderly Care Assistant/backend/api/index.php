<?php

declare(strict_types=1);

date_default_timezone_set('Asia/Shanghai');

require_once __DIR__ . '/config/AppConfig.php';
require_once __DIR__ . '/lib/Response.php';
require_once __DIR__ . '/lib/Storage.php';
require_once __DIR__ . '/lib/Logger.php';
require_once __DIR__ . '/lib/AiClient.php';
require_once __DIR__ . '/utils/Request.php';
require_once __DIR__ . '/utils/Security.php';
require_once __DIR__ . '/services/SystemStateService.php';
require_once __DIR__ . '/services/FallDetectionService.php';
require_once __DIR__ . '/services/GemmaDecisionService.php';
require_once __DIR__ . '/services/EmergencyService.php';
require_once __DIR__ . '/services/VideoStreamService.php';
require_once __DIR__ . '/services/AiUpdateService.php';
require_once __DIR__ . '/services/MockScenarioService.php';
require_once __DIR__ . '/controllers/StatusController.php';
require_once __DIR__ . '/controllers/FallDetectionController.php';
require_once __DIR__ . '/controllers/GemmaDecisionController.php';
require_once __DIR__ . '/controllers/EmergencyController.php';
require_once __DIR__ . '/controllers/VideoStreamController.php';
require_once __DIR__ . '/controllers/AiUpdateController.php';
require_once __DIR__ . '/controllers/DemoController.php';
require_once __DIR__ . '/controllers/LogController.php';

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    Response::json(['ok' => true]);
}

$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) ?: '/';
$path = preg_replace('#^/api#', '', $path);
$method = $_SERVER['REQUEST_METHOD'];

$config = AppConfig::get();
Security::validate($config);

$storage = new Storage(__DIR__ . '/storage');
$logger = new Logger(__DIR__ . '/../logs/system.log');
$stateService = new SystemStateService($storage);
$mockScenarioService = new MockScenarioService(dirname(__DIR__, 2) . '/mock');
$fallDetectionService = new FallDetectionService($stateService);
$gemmaDecisionService = new GemmaDecisionService($stateService);
$emergencyService = new EmergencyService($stateService, $logger);
$videoStreamService = new VideoStreamService($config);
$aiUpdateService = new AiUpdateService($stateService, $logger);

try {
    if ($method === 'GET' && $path === '/status') {
        (new StatusController($stateService, $logger))->show();
    }

    if ($method === 'POST' && $path === '/status/analyze') {
        (new StatusController($stateService, $logger))->analyze();
    }

    if ($method === 'GET' && $path === '/fall-detection') {
        (new FallDetectionController($fallDetectionService, $stateService))->show();
    }

    if ($method === 'GET' && $path === '/gemma-decision') {
        (new GemmaDecisionController($gemmaDecisionService))->show();
    }

    if ($method === 'POST' && $path === '/emergency') {
        (new EmergencyController($emergencyService))->trigger();
    }

    if ($method === 'POST' && $path === '/ai-update') {
        (new AiUpdateController($aiUpdateService))->store();
    }

    if ($method === 'GET' && $path === '/video-stream') {
        (new VideoStreamController($videoStreamService))->show();
    }

    if ($method === 'POST' && $path === '/demo') {
        (new DemoController($stateService, $mockScenarioService, $logger))->simulate();
    }

    if ($method === 'GET' && $path === '/logs') {
        (new LogController($logger))->index();
    }

    Response::error('API route not found.', 404);
} catch (Throwable $exception) {
    $logger->error('Unhandled API error: ' . $exception->getMessage());
    Response::error('Internal server error.', 500, [
        'detail' => $exception->getMessage(),
    ]);
}

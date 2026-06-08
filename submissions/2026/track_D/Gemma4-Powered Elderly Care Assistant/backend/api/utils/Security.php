<?php

declare(strict_types=1);

final class Security
{
    /**
     * Optional bearer token validation. Empty configured token means demo mode.
     */
    public static function validate(array $config): void
    {
        $expected = $config['api_token'] ?? '';
        if ($expected === '') {
            return;
        }

        $header = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
        $actual = str_replace('Bearer ', '', $header);
        if (!hash_equals($expected, $actual)) {
            Response::error('Unauthorized API request.', 401);
        }
    }
}

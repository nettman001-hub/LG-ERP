<?php

require_once __DIR__ . '/otp_bridge_common.php';

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    otp_send_json(array(
        'ok' => false,
        'error' => 'GET only',
    ), 405);
}

$logFile = __DIR__ . '/otp_log.txt';
if (!is_file($logFile)) {
    otp_send_json(array(
        'ok' => false,
    ), 200);
}

$handle = @fopen($logFile, 'c+');
if ($handle === false) {
    otp_send_json(array(
        'ok' => false,
        'error' => 'Failed to open OTP log file',
    ), 500);
}

if (!flock($handle, LOCK_EX)) {
    fclose($handle);
    otp_send_json(array(
        'ok' => false,
        'error' => 'Failed to lock OTP log file',
    ), 500);
}

rewind($handle);
$raw = stream_get_contents($handle);
if ($raw === false || trim($raw) === '') {
    flock($handle, LOCK_UN);
    fclose($handle);
    otp_send_json(array(
        'ok' => false,
    ), 200);
}

$lines = preg_split('/\r\n|\r|\n/', trim($raw));
$code = '';
$createdAt = '';

for ($i = count($lines) - 1; $i >= 0; $i--) {
    $line = trim((string)$lines[$i]);
    if ($line === '') {
        continue;
    }

    $code = otp_extract_code($line);
    if ($code === '') {
        continue;
    }

    if (preg_match('/^\[([^\]]+)\]/', $line, $matches) === 1) {
        $createdAt = trim($matches[1]);
    }
    break;
}

if ($code === '') {
    flock($handle, LOCK_UN);
    fclose($handle);
    otp_send_json(array(
        'ok' => false,
    ), 200);
}

rewind($handle);
if (!ftruncate($handle, 0)) {
    flock($handle, LOCK_UN);
    fclose($handle);
    otp_send_json(array(
        'ok' => false,
        'error' => 'Failed to clear OTP log file',
    ), 500);
}

fflush($handle);
flock($handle, LOCK_UN);
fclose($handle);

otp_send_json(array(
    'ok' => true,
    'code' => $code,
    'created_at' => $createdAt,
), 200);

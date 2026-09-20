<?php

require_once __DIR__ . '/otp_bridge_common.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    otp_send_json(array(
        'ok' => false,
        'error' => 'POST only',
    ), 405);
}

$payload = otp_read_input_json();

$code = '';
if (isset($payload['code'])) {
    $code = otp_extract_code($payload['code']);
}
if ($code === '' && isset($_POST['code'])) {
    $code = otp_extract_code($_POST['code']);
}

if ($code === '') {
    otp_send_json(array(
        'ok' => false,
        'error' => 'Valid 6-digit code is required',
    ), 400);
}

$createdAt = '';
if (isset($payload['created_at'])) {
    $createdAt = (string)$payload['created_at'];
}
if ($createdAt === '' && isset($_POST['created_at'])) {
    $createdAt = (string)$_POST['created_at'];
}
if ($createdAt === '' || strtotime($createdAt) === false) {
    $createdAt = gmdate('c');
}

$saved = otp_save_store(array(
    'code' => $code,
    'created_at' => $createdAt,
    'uploaded_at' => gmdate('c'),
));

if (!$saved) {
    otp_send_json(array(
        'ok' => false,
        'error' => 'Failed to save OTP',
    ), 500);
}

otp_send_json(array(
    'ok' => true,
    'code' => $code,
    'created_at' => $createdAt,
), 200);

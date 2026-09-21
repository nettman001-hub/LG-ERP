<?php

define('OTP_STORE_FILE', __DIR__ . '/otp_store.json');
define('OTP_TTL_SECONDS', 180);

function otp_send_json($data, $statusCode)
{
    if ($statusCode === null) {
        $statusCode = 200;
    }
    http_response_code($statusCode);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data);
    exit;
}

function otp_read_input_json()
{
    $raw = file_get_contents('php://input');
    if ($raw === false || trim($raw) === '') {
        return array();
    }

    $decoded = json_decode($raw, true);
    if (!is_array($decoded)) {
        return array();
    }
    return $decoded;
}

function otp_extract_code($value)
{
    $value = (string)$value;
    if (preg_match('/\b(\d{6})\b/', $value, $matches) === 1) {
        return $matches[1];
    }
    return '';
}

function otp_load_store()
{
    if (!is_file(OTP_STORE_FILE)) {
        return null;
    }

    $raw = file_get_contents(OTP_STORE_FILE);
    if ($raw === false || trim($raw) === '') {
        return null;
    }

    $data = json_decode($raw, true);
    if (!is_array($data)) {
        return null;
    }
    return $data;
}

function otp_save_store($data)
{
    $json = json_encode($data);
    if ($json === false) {
        return false;
    }

    return file_put_contents(OTP_STORE_FILE, $json, LOCK_EX) !== false;
}

function otp_delete_store()
{
    if (!is_file(OTP_STORE_FILE)) {
        return true;
    }
    return unlink(OTP_STORE_FILE);
}

function otp_is_expired($data)
{
    if (!$data || !is_array($data)) {
        return true;
    }

    $createdAt = '';
    if (isset($data['created_at'])) {
        $createdAt = (string)$data['created_at'];
    }
    if ($createdAt === '') {
        return true;
    }

    $createdTs = strtotime($createdAt);
    if ($createdTs === false) {
        return true;
    }

    return (time() - $createdTs) > OTP_TTL_SECONDS;
}

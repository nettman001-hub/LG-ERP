<?php

require_once __DIR__ . '/otp_bridge_common.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    otp_send_json(array(
        'ok' => false,
        'error' => 'POST only',
    ), 405);
}

$deleted = otp_delete_store();

otp_send_json(array(
    'ok' => $deleted ? true : false,
), 200);

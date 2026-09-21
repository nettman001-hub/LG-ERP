<?php

define('INVENTORY_DB_HOST', 'localhost');
define('INVENTORY_DB_NAME', 'nettman001');
define('INVENTORY_DB_USER', 'nettman001');
define('INVENTORY_DB_PASSWORD', 'chak4628!!');
define('INVENTORY_QUEUE_TABLE', 'erp_queue');

// Leave this empty for immediate use, or set a shared secret and send it via X-Bridge-Token.
define('INVENTORY_BRIDGE_TOKEN', '');

function inventory_send_json($data, $statusCode = 200)
{
    http_response_code($statusCode);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function inventory_read_input_json()
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

function inventory_bridge_require_auth()
{
    $expected = trim((string)INVENTORY_BRIDGE_TOKEN);
    if ($expected === '') {
        return;
    }

    $provided = '';
    if (isset($_SERVER['HTTP_X_BRIDGE_TOKEN'])) {
        $provided = trim((string)$_SERVER['HTTP_X_BRIDGE_TOKEN']);
    } elseif (isset($_GET['token'])) {
        $provided = trim((string)$_GET['token']);
    } elseif (isset($_POST['token'])) {
        $provided = trim((string)$_POST['token']);
    }

    if ($provided === '' || !hash_equals($expected, $provided)) {
        inventory_send_json(array(
            'ok' => false,
            'error' => 'Unauthorized',
        ), 401);
    }
}

function inventory_bridge_limit($default = 5, $max = 20)
{
    $raw = isset($_GET['limit']) ? (int)$_GET['limit'] : $default;
    if ($raw < 1) {
        $raw = $default;
    }
    if ($raw > $max) {
        $raw = $max;
    }
    return $raw;
}

function inventory_bridge_pdo()
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $dsn = sprintf(
        'mysql:host=%s;dbname=%s;charset=utf8mb4',
        INVENTORY_DB_HOST,
        INVENTORY_DB_NAME
    );

    $pdo = new PDO($dsn, INVENTORY_DB_USER, INVENTORY_DB_PASSWORD, array(
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ));

    return $pdo;
}


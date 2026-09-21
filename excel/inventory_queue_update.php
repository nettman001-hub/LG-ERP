<?php

require_once __DIR__ . '/inventory_bridge_common.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    inventory_send_json(array(
        'ok' => false,
        'error' => 'POST only',
    ), 405);
}

inventory_bridge_require_auth();

$payload = inventory_read_input_json();

$id = 0;
if (isset($payload['id'])) {
    $id = (int)$payload['id'];
} elseif (isset($_POST['id'])) {
    $id = (int)$_POST['id'];
}

$status = '';
if (isset($payload['status'])) {
    $status = strtoupper(trim((string)$payload['status']));
} elseif (isset($_POST['status'])) {
    $status = strtoupper(trim((string)$_POST['status']));
}

$resultText = null;
if (array_key_exists('result_text', $payload)) {
    $resultText = (string)$payload['result_text'];
} elseif (isset($_POST['result_text'])) {
    $resultText = (string)$_POST['result_text'];
}

if ($id <= 0) {
    inventory_send_json(array(
        'ok' => false,
        'error' => 'Valid id is required',
    ), 400);
}

if ($status !== 'DONE' && $status !== 'FAIL') {
    inventory_send_json(array(
        'ok' => false,
        'error' => 'Status must be DONE or FAIL',
    ), 400);
}

try {
    $pdo = inventory_bridge_pdo();
    $table = INVENTORY_QUEUE_TABLE;

    $stmt = $pdo->prepare(
        "UPDATE `{$table}`
         SET status = :status,
             result_text = :result_text
         WHERE id = :id"
    );
    $stmt->bindValue(':status', $status, PDO::PARAM_STR);
    $stmt->bindValue(':result_text', $resultText, PDO::PARAM_STR);
    $stmt->bindValue(':id', $id, PDO::PARAM_INT);
    $stmt->execute();

    inventory_send_json(array(
        'ok' => true,
        'id' => $id,
        'status' => $status,
        'updated_rows' => $stmt->rowCount(),
    ));
} catch (Throwable $e) {
    inventory_send_json(array(
        'ok' => false,
        'error' => $e->getMessage(),
    ), 500);
}

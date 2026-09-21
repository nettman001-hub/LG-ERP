<?php

require_once __DIR__ . '/inventory_bridge_common.php';

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    inventory_send_json(array(
        'ok' => false,
        'error' => 'GET only',
    ), 405);
}

inventory_bridge_require_auth();

try {
    $pdo = inventory_bridge_pdo();
    $table = INVENTORY_QUEUE_TABLE;
    $limit = inventory_bridge_limit(5, 20);

    $countStmt = $pdo->query("SELECT COUNT(*) AS cnt FROM `{$table}` WHERE status = 'WAIT'");
    $waitingCount = (int)$countStmt->fetchColumn();

    $stmt = $pdo->prepare(
        "SELECT id, kakao_user_id, query_text, status, created_at
         FROM `{$table}`
         WHERE status = 'WAIT'
         ORDER BY id ASC
         LIMIT :limit"
    );
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->execute();
    $items = $stmt->fetchAll();

    inventory_send_json(array(
        'ok' => true,
        'waiting_count' => $waitingCount,
        'items' => $items,
        'server_time' => gmdate('c'),
    ));
} catch (Throwable $e) {
    inventory_send_json(array(
        'ok' => false,
        'error' => $e->getMessage(),
    ), 500);
}


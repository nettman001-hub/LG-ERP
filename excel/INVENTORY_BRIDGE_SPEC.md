# Inventory Queue Bridge

`main.py` now polls the Kakao queue through PHP instead of connecting to MariaDB directly.

## Files to Upload

Upload these files to `http://unione24.co.kr/api/inventory/`.

- `inventory_bridge_common.php`
- `inventory_queue_pull.php`
- `inventory_queue_update.php`

## Queue Flow

1. Kakao webhook inserts a row into `erp_queue` with `status='WAIT'`.
2. `main.py` polls `inventory_queue_pull.php` every 2.5 seconds by default.
3. The background worker resolves the model and collects:
   - ERP inventory
   - ERP production plan
   - Danawa lowest price
4. `main.py` writes the result back through `inventory_queue_update.php`.

## Optional Auth

If you want to protect the bridge endpoints:

1. Set `INVENTORY_BRIDGE_TOKEN` in `inventory_bridge_common.php`
2. Set the same token on the Windows PC before launching `main.py`

PowerShell example:

```powershell
$env:INVENTORY_BRIDGE_TOKEN="change-this-secret"
python main.py
```

## Optional Runtime Settings

`main.py` supports these environment variables:

- `INVENTORY_BRIDGE_BASE_URL`
- `INVENTORY_BRIDGE_TOKEN`
- `INVENTORY_BRIDGE_POLL_SECONDS`

Example:

```powershell
$env:INVENTORY_BRIDGE_BASE_URL="http://unione24.co.kr/api/inventory"
$env:INVENTORY_BRIDGE_POLL_SECONDS="2.5"
python main.py
```

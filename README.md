# Lab Work 4 — Data Storage and Replication

## Chosen variant
Variant A-2: local RustFS (S3-compatible) + Redis primary/replica. No AWS account or AWS keys are needed.

## Requirements
- Docker Desktop with Docker Compose
- Python 3.10+
- PowerShell (commands below)

## 1. Start storage services
From this project folder:
```powershell
docker compose up -d
docker compose ps
```
RustFS console: http://127.0.0.1:9001 (credentials: `lab4user` / `lab4password`).
If needed, console path: http://127.0.0.1:9001/rustfs/console/

## 2. Create Python environment and install dependencies
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 3. Configure environment and run the service
Run these commands in the same PowerShell window:
```powershell
$env:BUCKET = "lab4-files"
$env:S3_ENDPOINT = "http://127.0.0.1:9000"
$env:AWS_ACCESS_KEY_ID = "lab4user"
$env:AWS_SECRET_ACCESS_KEY = "lab4password"
$env:AWS_REGION = "us-east-1"
$env:REDIS_HOST = "127.0.0.1"
$env:REDIS_PRIMARY_PORT = "6379"
$env:REDIS_REPLICA_PORT = "6380"
python app.py
```
Keep this window running. Open another PowerShell window for API tests.

## 4. Part A — object storage checks
Save a file:
```powershell
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/files -ContentType "application/json" -Body '{"text":"Hello from Lab 4"}'
$r
$id = $r.file_id
```
Read it:
```powershell
Invoke-RestMethod "http://127.0.0.1:5000/files/$id"
```
Test a missing file (expect HTTP 404):
```powershell
try { Invoke-WebRequest "http://127.0.0.1:5000/files/00000000-0000-0000-0000-000000000000" } catch { $_.Exception.Response.StatusCode.value__ }
```
Persistence check:
1. Save `$id` from the save response.
2. Stop Flask with Ctrl+C.
3. Start Flask again with the same environment variables.
4. Read the same `$id`; it must still exist.
5. Optional stronger check: `docker compose up -d --force-recreate s3`, then read the same file. The named volume `s3-data` should preserve the object.

## 5. Part B — verify replication
```powershell
docker compose exec redis-primary redis-cli INFO replication
docker compose exec redis-replica redis-cli INFO replication
```
Expected roles: primary reports `role:master` and one connected replica; replica reports `role:slave` (Redis 7 terminology) and `master_link_status:up`.

## 6. Run E1
Reset the counter before the experiment:
```powershell
docker compose exec redis-primary redis-cli DEL counter
python scripts/experiment_e1.py
```
The script writes 100 times and immediately reads primary and replica. It prints the mismatch count and writes a CSV-like log to `logs/e1_results.csv`.

## 7. E2 — replica lag and recovery
Record the current primary and replica values first. Detach the replica:
```powershell
docker compose exec redis-replica redis-cli REPLICAOF NO ONE
```
Perform 10 writes and compare both reads:
```powershell
1..10 | ForEach-Object { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/counter/increment }
Invoke-RestMethod "http://127.0.0.1:5000/counter?from=primary"
Invoke-RestMethod "http://127.0.0.1:5000/counter?from=replica"
```
Restore replication and measure catch-up:
```powershell
$start = Get-Date
docker compose exec redis-replica redis-cli REPLICAOF redis-primary 6379
# Repeat the replica GET until its value equals the primary value, then:
(Get-Date) - $start
```
Record the before/after values and elapsed time in the report/logs.

## 8. E3 — read your own write
Detach again with `REPLICAOF NO ONE`. Make three increments; after each increment call:
```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/counter/increment
Invoke-RestMethod "http://127.0.0.1:5000/counter?from=primary"
Invoke-RestMethod "http://127.0.0.1:5000/counter?from=replica"
```
Record the three pairs. Restore with `REPLICAOF redis-primary 6379`.

## 9. E4 — manual failover
1. Stop the primary:
   `docker compose stop redis-primary`
2. Read from replica (should work); increment through API (should return HTTP 503 because the service still writes to the old primary).
3. Promote replica:
   `docker compose exec redis-replica redis-cli REPLICAOF NO ONE`
4. Restart the Flask service after setting:
   `$env:REDIS_PRIMARY_PORT = "6380"`
   Then call `POST /counter/increment` and read `GET /counter?from=primary`.
5. Bring old primary back:
   `docker compose start redis-primary`
6. Inspect both nodes:
   `docker compose exec redis-primary redis-cli INFO replication`
   `docker compose exec redis-replica redis-cli INFO replication`
   Both may report `role:master`. Record each counter value. This is split-brain: the nodes accept independent writes and their data can diverge.
7. After recording the divergent values, reconfigure the **running** old primary as a replica of the promoted node:
```powershell
docker compose exec redis-primary redis-cli REPLICAOF redis-replica 6379
docker compose exec redis-primary redis-cli INFO replication
docker compose exec redis-primary redis-cli GET counter
docker compose exec redis-replica redis-cli GET counter
```
Confirm `role:slave`, `master_link_status:up`, and matching values. The old master's divergent data may be overwritten.

During the observed failover run, port 5000 was occupied by an older Flask process. To run this project on port 5050 without changing code, set `$env:APP_PORT = "5050"` in the **same** PowerShell session before `python app.py`, and use `http://127.0.0.1:5050` for requests. With failover, set `$env:REDIS_PRIMARY_PORT = "6380"` (and optionally `$env:REDIS_REPLICA_PORT = "6380"` for temporary API reads). The original `docker-compose.yml` topology may reapply on container recreation.

## 10. Evidence and submission
- Save terminal outputs in `logs/`.
- Save screenshots in `screenshots/`: file save/read, 404, service restart/read, object in RustFS console, both Redis replication INFO outputs, and E1–E4.
- See `report.md` for measured values and recovery time. The assignment handout requests PDF; this package uses Markdown at the student’s request.
- ZIP the project folder. Do not include `.venv`, AWS keys, or local credentials.

## Notes
- Redis uses the term `slave` in INFO output for compatibility, although the primary/replica terminology is used in this report.
- `REPLICAOF NO ONE` safely detaches/promotes a node; the lab handout's example `REPLICAOF 127.0.0.1 1` is not a reliable way to simulate a disconnected replica.

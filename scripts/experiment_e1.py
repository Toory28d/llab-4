import csv
import os
import time
from pathlib import Path

import requests

BASE = os.environ.get("LAB4_BASE_URL", "http://127.0.0.1:5000")
OUT = Path(__file__).resolve().parents[1] / "logs" / "e1_results.csv"

rows = []
stale = 0
for i in range(1, 101):
    write = requests.post(f"{BASE}/counter/increment", timeout=5)
    write.raise_for_status()
    primary = requests.get(f"{BASE}/counter?from=primary", timeout=5)
    primary.raise_for_status()
    replica = requests.get(f"{BASE}/counter?from=replica", timeout=5)
    replica.raise_for_status()
    a = primary.json()["value"]
    b = replica.json()["value"]
    mismatch = a != b
    stale += int(mismatch)
    rows.append([i, a, b, mismatch])
    time.sleep(0.005)

OUT.parent.mkdir(exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["iteration", "primary_value", "replica_value", "stale_read"])
    writer.writerows(rows)

print(f"stale reads from the replica: {stale} out of 100")
print(f"Detailed results: {OUT}")

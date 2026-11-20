# Lab Work 4 — Data Storage and Replication

**Student:** Denis Essaulov  
**Variant:** Local RustFS (S3-compatible object storage) + Redis Primary/Replica  
**Report format:** Markdown; recorded experimental results from the local environment

## 1. Objective and setup

The lab demonstrates durable object storage, asynchronous Redis replication, stale reads, manual failover, and split-brain. Flask exposes `POST /files`, `GET /files/{file_id}`, `POST /counter/increment`, and `GET /counter?from=primary|replica`. RustFS runs on host port 9000, and Redis nodes initially use host ports 6379 (primary) and 6380 (replica). Redis-to-Redis traffic inside Docker uses port 6379.

## 2. Part A — Object storage

- `POST /files` with `{"text":"Hello from Lab 4"}` returned **HTTP 201** and a generated file identifier.
- `GET /files/{file_id}` returned **HTTP 200** and the saved text `Hello from Lab 4`.
- A request for a nonexistent identifier returned **HTTP 404**.
- The stored object was inspected in the RustFS console. File persistence across the application restart was checked during the lab.
- The RustFS named Docker volume `s3-data` keeps object data outside the lifecycle of the Flask process.

## 3. Part B — Experiments

| Experiment | Procedure | Observed result | Interpretation |
|---|---|---|---|
| **E1 — Normal replication** | Perform 100 writes and read primary and replica after each write. | **0 stale reads / 100** in the verified run; both nodes matched for values 1–100. | Local replication caught up before the sampled reads; this does **not** guarantee synchronous replication. |
| **E2 — Replica disconnected** | Detach replica; perform 10 increments; reconnect replica and time recovery. | Primary **10**, detached replica **0**; catch-up time **1.563 s**. | A detached replica serves stale data, then converges after replication resumes. |
| **E3 — Read your own write** | Start at 101/101, detach replica, then write and immediately read both nodes three times. | Primary **102, 103, 104**; replica **101, 101, 101**. | Reading from the replica did not satisfy read-your-own-write consistency. |
| **E4 — Failover and split-brain** | Stop original primary, promote replica, redirect Flask writes to port 6380, restart original primary, then restore replication. | Successful promoted-master API write: **107**. After restart: old primary **104**, promoted master **107**, both `role:master`. After old primary became replica: **107/107**; next API write: **108/108**. | Manual failover restored writes, but the independently restarted old primary caused split-brain. Reconfiguration restored a single-master topology. |

**E1 evidence:** `logs/e1_results.csv` contains the 100 observed read pairs. An earlier diagnostic E1 run showed stale values while replication was disconnected; the table reports the verified run after replication was restored.

### E4 recovery details

The old primary was reconfigured with `REPLICAOF redis-replica 6379`. Its `INFO replication` then reported `role:slave`, `master_host:redis-replica`, `master_link_status:up`, and `master_sync_in_progress:0`. Both nodes returned 107. The next `POST /counter/increment` through Flask on host port **5050** returned `{"source":"primary","value":108}`; both Redis containers then returned 108. The application used host port 5050 during failover troubleshooting because port 5000 was serving an older application instance.

## 4. Reflection questions

**1. Why not store files on a container's disk? Why object storage?**  
Container-local writable layers may disappear when containers are removed or replaced and are not a reliable shared persistence mechanism. Object storage separates file data from the application process, provides stable object identifiers and API access, and can use persistent volumes or managed storage for durability. In this lab, RustFS used the named `s3-data` volume.

**2. What are replication lag and eventual consistency? What did E1 and E2 show?**  
Replication lag is the delay between a write being committed on the primary and becoming visible on a replica. Eventual consistency means replicas can temporarily differ but converge if updates and replication resume. E1 showed 0 stale reads in 100 local samples, which does not eliminate the possibility of lag. In E2, the disconnected replica stayed at 0 while the primary reached 10, then caught up after reconnection in 1.563 seconds.

**3. When are replica reads acceptable?**  
Replica reads are suitable when slight staleness is tolerable, such as viewing noncritical statistics or a public content feed. They are unsuitable when a user must immediately see their own update, such as confirming a payment or checking a newly changed account balance. E3 showed that the replica kept returning 101 after writes advanced the primary to 102, 103, and 104.

**4. What was manual during failure? What happened when the old primary returned? What changes with automatic failover?**  
We stopped the original primary, manually promoted the replica with `REPLICAOF NO ONE`, and redirected the Flask Redis write endpoint to host port 6380. On restart, the old primary independently reported `role:master`; both masters had different counter values (104 and 107). We manually reconfigured the old node as a replica of the promoted master. An automatic failover system with leader election and coordination can detect failures and elect a new leader, reducing manual intervention and the risk of concurrent leaders. In MongoDB replica sets (covered in Lab 5), elections choose a primary; clients still need appropriate retry and discovery behavior. Automatic failover does not imply zero lag or zero risk of losing unreplicated writes.

## 5. Conclusion

Object storage preserved files independently of the Flask process. Redis asynchronous replication provided fast replica reads in normal conditions but allowed stale reads during disconnection. Manual promotion restored availability, while the return of the old master demonstrated split-brain and divergent state. Reattaching the old master as a replica restored consistent values and propagation of new writes.

## 6. Evidence and reproducibility

- `logs/e1_results.csv`: recorded E1 values and stale-read flags (100 rows).
- `logs/e2_e4_observations.md`: transcribed measurements and command results from the terminal session.
- `app.py`, `requirements.txt`, `docker-compose.yml`, `spec.md`: implementation and version 3 specification.
- Screenshots are **not included as verified image evidence** in this archive; add your own labeled screenshots if the instructor requires them.

**Note:** `spec.md` uses provisional requirement IDs R1–R8; reconcile these with Lab 2/3 numbering if your course requires continuity. No live AWS credentials are included.

# Recorded E2–E4 observations

These values were transcribed from the user's terminal results during the laboratory session; this is not a raw terminal capture.

## E2
- Replica detached using `REPLICAOF NO ONE`.
- After 10 writes: primary `10`, detached replica `0`.
- Replica reconnected; measured catch-up: `1.563 seconds`.

## E3
- Before test: primary `101`, replica `101`.
- After write 1: primary `102`, replica `101`.
- After write 2: primary `103`, replica `101`.
- After write 3: primary `104`, replica `101`.

## E4
- `docker compose exec redis-replica redis-cli INFO replication` showed `role:master` after promotion.
- Direct Redis `INCR counter` returned `106` during troubleshooting.
- Flask on host port `5050` successfully returned `source=primary, value=107`.
- Old primary restarted: `role:master`, `counter=104`.
- Promoted replica: `role:master`, `counter=107`.
- `docker compose exec redis-primary redis-cli REPLICAOF redis-replica 6379` returned `OK` (console showed an extra encoding character).
- Old primary then reported `role:slave`, `master_host:redis-replica`, `master_link_status:up`, `master_sync_in_progress:0`.
- Both nodes returned `107`.
- Subsequent API increment returned `source=primary, value=108`.
- Both nodes returned `108`.

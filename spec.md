# Service Specification — Version 3

## Overview
The service exposes a time endpoint, stores text files in S3-compatible object storage, and uses Redis primary/replica nodes for a counter. Files are not stored on the Flask container or process disk.

## Assumptions
- The service runs locally on `http://127.0.0.1:5000`.
- RustFS provides an S3-compatible API at `http://127.0.0.1:9000`.
- Redis primary and replica are reachable at ports `6379` and `6380`.
- Maximum text-file size is 1 MiB (1,048,576 bytes).
- Writes go only to the Redis primary. A read from the replica may return a stale value while replication is delayed or disconnected (eventual consistency).
- Redis and object-storage failures are reported as HTTP 503.

## Functional requirements
> Requirement IDs below are provisional R1–R8. If Lab 2/Lab 3 already defined requirement IDs, renumber these sequentially to continue that existing series before submission.

| ID | Requirement |
|---|---|
| R1 | `GET /time` shall return the current UTC time and service identifier with HTTP 200. |
| R2 | `POST /files` shall accept JSON containing a string field `text`, store it as an object in the configured bucket, and return a UUID `file_id` with HTTP 201. |
| R3 | `POST /files` shall return HTTP 400 when the body is invalid or the UTF-8 file exceeds 1 MiB. |
| R4 | `GET /files/{file_id}` shall return the stored text and identifier with HTTP 200, or HTTP 404 when the identifier/object does not exist. |
| R5 | Object-storage errors shall return HTTP 503. File contents shall persist independently of the Flask process and service restart. |
| R6 | `POST /counter/increment` shall increment the `counter` key on the configured Redis primary only and return the new value with HTTP 200. |
| R7 | `GET /counter?from=primary` and `GET /counter?from=replica` shall read from the selected Redis node and return its value and source with HTTP 200. Replica reads are allowed to be stale. |
| R8 | Redis unavailability shall return HTTP 503; an invalid `from` query value shall return HTTP 400. Redis node addresses and ports shall be configurable through environment variables. |

## API examples

### Save a file
`POST /files`
```json
{"text": "Hello from Lab 4"}
```
Success: `201 Created`
```json
{"file_id": "generated-uuid"}
```

### Read a file
`GET /files/{file_id}`
Success: `200 OK`
```json
{"file_id": "generated-uuid", "text": "Hello from Lab 4"}
```

### Counter
- `POST /counter/increment` — increments on primary.
- `GET /counter?from=primary` — reads primary.
- `GET /counter?from=replica` — reads replica.

## Error responses
- `400 Bad Request` — invalid JSON/body, file too large, or invalid counter source.
- `404 Not Found` — requested file does not exist.
- `503 Service Unavailable` — object storage or Redis is unavailable.

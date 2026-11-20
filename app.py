import os
import uuid
from datetime import datetime, timezone

import boto3
import redis
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError
from flask import Flask, jsonify, request

app = Flask(__name__)

# Object storage (RustFS locally, or AWS S3 if configured without S3_ENDPOINT)
BUCKET = os.environ.get("BUCKET", "lab4-files")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
MAX_FILE_BYTES = int(os.environ.get("MAX_FILE_BYTES", str(1024 * 1024)))

s3 = boto3.client(
    "s3",
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    config=Config(s3={"addressing_style": "path"}) if S3_ENDPOINT else None,
)

def ensure_bucket():
    """Create the bucket if it does not exist."""
    try:
        s3.head_bucket(Bucket=BUCKET)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchBucket", "NotFound"):
            s3.create_bucket(Bucket=BUCKET)
        else:
            raise

# Redis endpoints are configurable so failover does not require a code change.
REDIS_HOST = os.environ.get("REDIS_HOST", "127.0.0.1")
primary = redis.Redis(
    host=REDIS_HOST,
    port=int(os.environ.get("REDIS_PRIMARY_PORT", "6379")),
    decode_responses=True,
    socket_timeout=2,
)
replica = redis.Redis(
    host=REDIS_HOST,
    port=int(os.environ.get("REDIS_REPLICA_PORT", "6380")),
    decode_responses=True,
    socket_timeout=2,
)

@app.get("/time")
def get_time():
    """Time endpoint retained from the previous laboratory service."""
    return jsonify({
        "utc": datetime.now(timezone.utc).isoformat(),
        "service": "lab4-storage-replication"
    }), 200

@app.post("/files")
def save_file():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        return jsonify({"error": "JSON body must contain a string field named 'text'"}), 400

    content = payload["text"].encode("utf-8")
    if len(content) > MAX_FILE_BYTES:
        return jsonify({"error": f"file exceeds {MAX_FILE_BYTES} byte limit"}), 400

    file_id = str(uuid.uuid4())
    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=f"files/{file_id}.txt",
            Body=content,
            ContentType="text/plain; charset=utf-8",
        )
    except (ClientError, BotoCoreError):
        return jsonify({"error": "object storage unavailable"}), 503

    return jsonify({"file_id": file_id}), 201

@app.get("/files/<file_id>")
def read_file(file_id):
    # UUID validation prevents arbitrary object-key access.
    try:
        normalized_id = str(uuid.UUID(file_id))
    except (ValueError, AttributeError):
        return jsonify({"error": "file not found"}), 404

    try:
        obj = s3.get_object(Bucket=BUCKET, Key=f"files/{normalized_id}.txt")
        content = obj["Body"].read().decode("utf-8")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404", "NotFound"):
            return jsonify({"error": "file not found"}), 404
        return jsonify({"error": "object storage unavailable"}), 503
    except (BotoCoreError, UnicodeDecodeError):
        return jsonify({"error": "object storage unavailable"}), 503

    return jsonify({"file_id": normalized_id, "text": content}), 200

@app.post("/counter/increment")
def increment():
    try:
        value = primary.incr("counter")
    except redis.exceptions.RedisError:
        return jsonify({"error": "storage unavailable"}), 503
    return jsonify({"value": value, "source": "primary"}), 200

@app.get("/counter")
def get_counter():
    source = request.args.get("from", "primary")
    if source not in ("primary", "replica"):
        return jsonify({"error": "from must be primary or replica"}), 400

    client = replica if source == "replica" else primary
    try:
        value = client.get("counter")
    except redis.exceptions.RedisError:
        return jsonify({"error": "storage unavailable"}), 503
    return jsonify({"value": int(value or 0), "source": source}), 200

if __name__ == "__main__":
    # For local RustFS, start docker compose before launching the Flask app.
    if os.environ.get("SKIP_BUCKET_CHECK") != "1":
        ensure_bucket()
    app.run(host="127.0.0.1", port=int(os.environ.get("APP_PORT", "5000")), debug=False)

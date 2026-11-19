# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

import asyncio
import json
import logging
import os
import shutil
import struct
import tarfile
import time
import uuid
from datetime import datetime
from io import BytesIO

import boto3
import jwt
import requests
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from llm_triage import (
    run_flush52_pipeline,
    run_fw_assert_pipeline,
    run_kfence_pipeline,
    run_log_summarization,
)
from pydantic import BaseModel

load_dotenv()

# Debug mode configuration
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "yes")

# Internal deployment configuration
INTERNAL_LOGSENSE = True


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("log-summarization")
log.propagate = False  # Prevent duplicate logs by disabling propagation to root logger

# Add handler to the named logger since we disabled propagation
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.addHandler(handler)

# Set log level based on debug mode
if DEBUG_MODE:
    log.setLevel(logging.DEBUG)
    log.debug("Debug mode enabled")
else:
    log.setLevel(logging.INFO)

if INTERNAL_LOGSENSE:
    log.info("Authentication is disabled for internal deployment")
    log.info("Portal API calls are disabled for internal deployment")
    log.info("S3 uploads are disabled for internal deployment")
    log.info("LogSense record creation is disabled for internal deployment")

SAVE_ROOT = os.getenv("LOG_SUMMARIZATION_DATA_DIR", "/local/mnt/log_summarization_api_data")
MAX_EXTRACT_BYTES = int(os.getenv("MAX_EXTRACT_BYTES", str(10 * 1024 * 1024 * 1024)))
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
PORTAL_DOMAIN = os.getenv("PORTAL_DOMAIN")
SERVICE_ACCOUNT_TOKEN = os.getenv("SERVICE_ACCOUNT_TOKEN")

os.makedirs(SAVE_ROOT, exist_ok=True)

app = FastAPI(title="Log Summarization Service")
security = HTTPBearer()


# ---------------------------------------------------------------------------
# INTERNAL_LOGSENSE: disk-based job persistence
# ---------------------------------------------------------------------------
# When INTERNAL_LOGSENSE is True there is no portal backend to store state.
# Each job gets its own directory under SAVE_ROOT:
#
#   {SAVE_ROOT}/{request_id}/
#       upload.tar          - original TAR file
#       extracted/          - extracted TAR contents
#       status.json         - job metadata & status
#       summary.txt         - LLM summary (written when COMPLETED)
# ---------------------------------------------------------------------------

def _get_internal_job_dir(request_id: str) -> str:
    """Return the directory path for an INTERNAL_LOGSENSE job."""
    return os.path.join(SAVE_ROOT, request_id)


def _read_internal_job(request_id: str) -> dict | None:
    """Read job status from disk for INTERNAL_LOGSENSE mode."""
    job_dir = _get_internal_job_dir(request_id)
    status_file = os.path.join(job_dir, "status.json")
    if not os.path.exists(status_file):
        return None
    try:
        with open(status_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to read status.json for {request_id}: {str(e)}")
        return None


def _write_internal_job(request_id: str, data: dict) -> None:
    """Write (overwrite) job status to disk for INTERNAL_LOGSENSE mode."""
    job_dir = _get_internal_job_dir(request_id)
    os.makedirs(job_dir, exist_ok=True)
    status_file = os.path.join(job_dir, "status.json")
    try:
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error(f"Failed to write status.json for {request_id}: {str(e)}")


def verify_jwt_token(authorization: str | None = Header(None), request: Request = None) -> dict:
    """
    Verify JWT token from Authorization header.

    When INTERNAL_LOGSENSE is enabled, returns a default payload with a placeholder UUID.
    """
    if INTERNAL_LOGSENSE:
        log.info("Authentication skipped due to INTERNAL_LOGSENSE setting")
        return {
            "sub": "internal-user",
            "app": "LogSense",
            "uid": "internal-device-uuid"
        }

    if DEBUG_MODE and request:
        log.debug("=== Request Headers ===")
        for header_name, header_value in request.headers.items():
            if header_name.lower() == "authorization":
                masked_value = f"{header_value[:20]}..." if len(header_value) > 20 else "***"
                log.debug(f"{header_name}: {masked_value}")
            else:
                log.debug(f"{header_name}: {header_value}")
        log.debug("======================")

    if not JWT_SECRET_KEY:
        log.error("JWT_SECRET_KEY not configured in environment variables")
        raise HTTPException(
            status_code=500,
            detail="JWT authentication not properly configured"
        )

    if not authorization:
        log.error("Authorization header is None or empty")
        if DEBUG_MODE and request:
            log.debug(f"All headers: {dict(request.headers)}")
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )

    if DEBUG_MODE:
        log.debug(f"Authorization header received (length: {len(authorization)})")

    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1]
    elif len(parts) == 1:
        token = parts[0]
    else:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected 'Bearer <token>' or plain token"
        )

    try:
        if DEBUG_MODE:
            log.debug(f"Attempting to decode JWT token with algorithm: {JWT_ALGORITHM}")

        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        if DEBUG_MODE:
            log.debug(f"JWT payload decoded successfully: {payload}")

        app_name = payload.get("app")
        if app_name != "LogSense":
            log.warning(f"Invalid app claim in JWT token. Expected 'LogSense', got '{app_name}'")
            raise HTTPException(
                status_code=403,
                detail="Access denied: Invalid app claim in token"
            )

        log.info(f"JWT token validated successfully for user: {payload.get('sub', 'unknown')}")
        return payload
    except jwt.ExpiredSignatureError:
        log.warning("JWT token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        log.warning(f"Invalid JWT token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        log.error(f"Unexpected error during JWT validation: {str(e)}")
        raise HTTPException(status_code=401, detail="Token validation failed")


def _upload_to_s3(file_path: str, s3_key: str) -> dict:
    """
    Upload a file to AWS S3 bucket.
    When INTERNAL_LOGSENSE is enabled, returns a mock response without uploading.
    """
    if INTERNAL_LOGSENSE:
        log.info(f"S3 upload skipped for {file_path} due to INTERNAL_LOGSENSE setting")
        return {
            "uploaded": True,
            "s3_url": f"file://{file_path}",
            "bucket": "local-storage",
            "key": s3_key,
            "skipped": True
        }
    bucket_name = os.getenv("S3_BUCKET_NAME")
    region = os.getenv("AWS_REGION", "us-east-1")

    if not bucket_name:
        log.warning("S3_BUCKET_NAME not configured, skipping S3 upload")
        return {"uploaded": False, "reason": "S3 bucket not configured"}

    try:
        s3_client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY")
        )
        s3_client.upload_file(file_path, bucket_name, s3_key)
        s3_url = f"s3://{bucket_name}/{s3_key}"
        log.info(f"Successfully uploaded {file_path} to {s3_url}")
        return {"uploaded": True, "s3_url": s3_url, "bucket": bucket_name, "key": s3_key}
    except ClientError as e:
        log.error(f"Failed to upload {file_path} to S3: {str(e)}")
        return {"uploaded": False, "reason": str(e)}
    except Exception as e:
        log.error(f"Unexpected error uploading {file_path} to S3: {str(e)}")
        return {"uploaded": False, "reason": str(e)}


def _commonpath_safe(a: str, b: str) -> bool:
    abs_a = os.path.abspath(a)
    abs_b = os.path.abspath(b)
    return os.path.commonpath([abs_a]) == os.path.commonpath([abs_a, abs_b])


def _validate_tar_members(tar: tarfile.TarFile, max_bytes: int):
    total = 0
    for m in tar.getmembers():
        name_norm = m.name.replace("\\", "/")
        if name_norm.startswith("/") or ".." in name_norm.split("/"):
            raise HTTPException(status_code=400, detail=f"Insecure path in archive: {m.name}")
        if m.islnk() or m.issym():
            raise HTTPException(status_code=400, detail=f"Symlinks are not allowed: {m.name}")
        if m.isfile():
            total += max(0, m.size or 0)
            if total > max_bytes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Archive too large (exceeds {max_bytes} bytes limit)."
                )


def _safe_extractall(tar: tarfile.TarFile, path: str):
    for m in tar.getmembers():
        if m.islnk() or m.issym():
            continue
        target_path = os.path.join(path, m.name)
        if not _commonpath_safe(path, target_path):
            raise HTTPException(status_code=400, detail=f"Path traversal detected: {m.name}")
    tar.extractall(path=path, members=[m for m in tar.getmembers() if not (m.islnk() or m.issym())])


def _make_upload_dir(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename or "upload"))[0] or "upload"
    uid = uuid.uuid4().hex[:8]
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    upload_dir = os.path.join(SAVE_ROOT, f"{stem}-{ts}-{uid}")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _detect_extracted_root(upload_dir: str) -> str:
    try:
        entries = os.listdir(upload_dir)
    except FileNotFoundError:
        return upload_dir
    if len(entries) == 1:
        only = os.path.join(upload_dir, entries[0])
        if os.path.isdir(only):
            return only
    return upload_dir


def _parse_cloud_meta_length(cloud_meta_ptr: bytes) -> int:
    """
    Parse cloud_meta_data length dynamically.
    Structure:
    - 32 bytes: service_name (fixed)
    - 1 byte: read_files (bool)
    - 1 byte: number_of_files
    - Variable: file paths (null-terminated strings) if read_files=true
    - Variable: data_types array (1 byte per file) if read_files=true
    """
    if len(cloud_meta_ptr) < 34:
        log.error("cloud_meta_data too short")
        return 0

    ptr = 32  # Skip service_name
    read_files = cloud_meta_ptr[ptr] != 0
    ptr += 1
    number_of_files = cloud_meta_ptr[ptr]
    ptr += 1

    if read_files and number_of_files > 0:
        for i in range(number_of_files):
            null_pos = cloud_meta_ptr[ptr:].find(b'\x00')
            if null_pos == -1:
                log.error("Malformed cloud_meta_data: no null terminator found")
                return 0
            ptr += null_pos + 1
            if ptr >= len(cloud_meta_ptr):
                log.error("cloud_meta_data exceeded buffer")
                return 0
        ptr += number_of_files
        if ptr > len(cloud_meta_ptr):
            log.error("cloud_meta_data exceeded buffer")
            return 0

    return ptr


def _strip_cia_headers(payload: bytes) -> bytes:
    """
    Strip CIA headers from the payload to extract the tar file.

    CIA response frame structure:
    1. sizeof(struct meta_data) - 16 bytes (8 uint16_t fields)
    2. cloud_meta_data - variable length
    3. 4 bytes - uint32_t for HTTP status code
    4. 4 bytes - uint32_t for headers_len
    5. headers_len bytes - HTTP response headers
    6. 4 bytes - uint32_t for body_len
    7. body - the actual tar file data
    """
    offset = 0

    META_DATA_SIZE = 16
    if len(payload) < META_DATA_SIZE:
        raise HTTPException(status_code=400, detail="Payload too short for meta_data")
    offset += META_DATA_SIZE
    log.info(f"Skipped meta_data: {META_DATA_SIZE} bytes")

    cloud_meta_ptr = payload[offset:]
    cloud_meta_len = _parse_cloud_meta_length(cloud_meta_ptr)
    if cloud_meta_len == 0:
        raise HTTPException(status_code=400, detail="Failed to parse cloud_meta_data")
    offset += cloud_meta_len
    log.info(f"Skipped cloud_meta_data: {cloud_meta_len} bytes")

    if len(payload) < offset + 4:
        raise HTTPException(status_code=400, detail="Payload too short for HTTP status")
    http_status = struct.unpack('<I', payload[offset:offset+4])[0]
    offset += 4
    log.info(f"HTTP status: {http_status}")

    if len(payload) < offset + 4:
        raise HTTPException(status_code=400, detail="Payload too short for headers_len")
    headers_len = struct.unpack('<I', payload[offset:offset+4])[0]
    offset += 4
    log.info(f"Headers length: {headers_len}")

    if len(payload) < offset + headers_len:
        raise HTTPException(status_code=400, detail="Payload too short for headers")
    offset += headers_len
    log.info(f"Skipped headers: {headers_len} bytes")

    if len(payload) < offset + 4:
        raise HTTPException(status_code=400, detail="Payload too short for body_len")
    body_len = struct.unpack('<I', payload[offset:offset+4])[0]
    offset += 4
    log.info(f"Body length: {body_len}")

    if len(payload) < offset + body_len:
        raise HTTPException(status_code=400, detail="Payload too short for body")
    tar_data = payload[offset:offset+body_len]
    log.info(f"Extracted tar data: {len(tar_data)} bytes")

    return tar_data


def _get_device_info(device_uuid: str) -> dict:
    """
    Call portal backend API to get device info from UUID.
    When INTERNAL_LOGSENSE is enabled, returns a mock device info response.
    """
    if INTERNAL_LOGSENSE:
        log.info(f"Portal API call skipped for device UUID {device_uuid} due to INTERNAL_LOGSENSE setting")
        return {
            "id": 12345,
            "oem_id": "internal-oem",
            "serial_number": device_uuid,
            "name": "Internal Device"
        }
    if not PORTAL_DOMAIN or not SERVICE_ACCOUNT_TOKEN:
        log.error("Portal API not configured (PORTAL_DOMAIN or SERVICE_ACCOUNT_TOKEN missing)")
        raise HTTPException(
            status_code=500,
            detail="Portal API not properly configured"
        )

    url = f"{PORTAL_DOMAIN}/device"
    headers = {"Authorization": f"Bearer {SERVICE_ACCOUNT_TOKEN}"}
    params = {"device_uuid": device_uuid}

    try:
        log.info(f"Calling portal API to get device info for UUID: {device_uuid}")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            log.error(f"Portal API returned non-success status: {data}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve device info: {data.get('message', 'Unknown error')}"
            )

        results = data.get("data", {}).get("results", [])
        if not results:
            log.error(f"No device found for UUID: {device_uuid}")
            raise HTTPException(
                status_code=404,
                detail=f"Device not found for UUID: {device_uuid}"
            )

        device_info = results[0]
        log.info(f"Successfully retrieved device info: {device_info}")
        return device_info

    except requests.exceptions.RequestException as e:
        log.error(f"Failed to call portal API for device info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve device info: {str(e)}"
        )


def _check_api_limit(oem_id: str) -> dict:
    """
    Call portal API to check if API limit has been reached.
    When INTERNAL_LOGSENSE is enabled, returns a mock response with no limits.
    """
    if INTERNAL_LOGSENSE:
        log.info(f"API limit check skipped for OEM ID {oem_id} due to INTERNAL_LOGSENSE setting")
        return {
            "count": 0,
            "max_count": None,
            "limit_reached": False,
            "counter_id": None,
            "company_name": "Internal Deployment",
            "skipped": True
        }
    if not PORTAL_DOMAIN or not SERVICE_ACCOUNT_TOKEN:
        log.error("Portal API not configured (PORTAL_DOMAIN or SERVICE_ACCOUNT_TOKEN missing)")
        raise HTTPException(
            status_code=500,
            detail="Portal API not properly configured"
        )

    url = f"{PORTAL_DOMAIN}/api-counter"
    headers = {"Authorization": f"Bearer {SERVICE_ACCOUNT_TOKEN}"}
    params = {"company_oem_id": oem_id, "api": "logsense"}

    try:
        log.info(f"Calling portal API to check API limit for OEM ID: {oem_id}")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])

        if not results:
            log.warning(f"No API counter found for OEM ID: {oem_id}")
            return {"count": 0, "max_count": None, "limit_reached": False, "counter_id": None}

        counter_info = results[0]
        count = counter_info.get("count", 0)
        max_count = counter_info.get("max_count")
        counter_id = counter_info.get("id")

        limit_reached = False
        if max_count is not None and count >= max_count:
            limit_reached = True
            log.error(f"API limit reached for OEM ID {oem_id}: {count}/{max_count}")
            raise HTTPException(
                status_code=429,
                detail=f"API limit reached. Current usage: {count}/{max_count}"
            )

        log.info(f"API limit check passed for OEM ID {oem_id}: {count}/{max_count if max_count else 'unlimited'}")
        return {
            "count": count,
            "max_count": max_count,
            "limit_reached": limit_reached,
            "company_name": counter_info.get("company_name"),
            "counter_id": counter_id
        }

    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        log.error(f"Failed to call portal API for API limit check: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check API limit: {str(e)}"
        )


def _create_logsense_record(device_id: int, input_s3_uri: str, file_size_bytes: int) -> dict:
    """
    Create a logsense record in the portal API with PENDING status.
    Returns dict with creation status, record 'id' (DB pk) and 'request_id' (UUID).
    """
    if not PORTAL_DOMAIN or not SERVICE_ACCOUNT_TOKEN:
        log.error("Portal API not configured (PORTAL_DOMAIN or SERVICE_ACCOUNT_TOKEN missing)")
        return {"created": False, "reason": "Portal API not configured"}

    url = f"{PORTAL_DOMAIN}/logsense"
    auth_headers = {
        "Authorization": f"Bearer {SERVICE_ACCOUNT_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "device": device_id,
        "input_s3_uri": input_s3_uri,
        "file_size_bytes": file_size_bytes,
    }

    try:
        log.info(f"Creating logsense record for device {device_id}")
        response = requests.post(url, headers=auth_headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        record_id = data.get("id")
        request_id = data.get("request_id")

        if not record_id or not request_id:
            log.warning(
                "Portal POST /logsense response missing 'id' or 'request_id' "
                "(portal may need redeployment). Falling back to GET /logsense."
            )
            try:
                get_response = requests.get(
                    f"{PORTAL_DOMAIN}/logsense",
                    headers={"Authorization": f"Bearer {SERVICE_ACCOUNT_TOKEN}"},
                    params={"device": device_id, "status": "PENDING", "ordering": "-created_at"},
                    timeout=10,
                )
                get_response.raise_for_status()
                results = get_response.json().get("results", [])
                if results:
                    record_id = results[0].get("id")
                    request_id = results[0].get("request_id")
                    log.info(
                        f"Fallback GET retrieved logsense record: "
                        f"id={record_id}, request_id={request_id}"
                    )
                else:
                    log.error("Fallback GET returned no results for device %s", device_id)
            except requests.exceptions.RequestException as ge:
                log.error(f"Fallback GET /logsense failed: {str(ge)}")

        log.info(f"Successfully created logsense record: id={record_id}, request_id={request_id}")
        return {
            "created": True,
            "id": record_id,
            "request_id": request_id,
            "response": data,
        }

    except requests.exceptions.RequestException as e:
        log.error(f"Failed to create logsense record: {str(e)}")
        return {"created": False, "reason": str(e)}


def _update_logsense_record(record_id, data: dict) -> dict:
    """
    PATCH a logsense record by its DB id (or disk-based key for INTERNAL_LOGSENSE).

    Args:
        record_id: DB primary key (int) or request_id (str) for INTERNAL_LOGSENSE
        data: Fields to update (e.g. {"status": "PROCESSING"})
    """
    if INTERNAL_LOGSENSE:
        # Read current state from disk, merge update, write back
        job = _read_internal_job(str(record_id))
        if job:
            job.update(data)
            _write_internal_job(str(record_id), job)
            log.info(f"INTERNAL_LOGSENSE: updated job {record_id}: {list(data.keys())}")
            return job
        log.warning(f"INTERNAL_LOGSENSE: job {record_id} not found for update")
        return {}

    if not PORTAL_DOMAIN or not SERVICE_ACCOUNT_TOKEN:
        log.error("Portal API not configured")
        return {"updated": False, "reason": "Portal API not configured"}

    url = f"{PORTAL_DOMAIN}/logsense/{record_id}"
    headers = {
        "Authorization": f"Bearer {SERVICE_ACCOUNT_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.patch(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log.error(f"Failed to update logsense record {record_id}: {str(e)}")
        return {"updated": False, "reason": str(e)}


def _get_logsense_record_by_request_id(request_id: str) -> dict | None:
    """
    Retrieve a logsense record by its request_id UUID.
    When INTERNAL_LOGSENSE is enabled, reads from disk.
    """
    if INTERNAL_LOGSENSE:
        return _read_internal_job(request_id)

    if not PORTAL_DOMAIN or not SERVICE_ACCOUNT_TOKEN:
        log.error("Portal API not configured")
        return None

    url = f"{PORTAL_DOMAIN}/logsense"
    headers = {"Authorization": f"Bearer {SERVICE_ACCOUNT_TOKEN}"}
    params = {"request_id": request_id}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        if results:
            return results[0]
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"Failed to get logsense record for request_id {request_id}: {str(e)}")
        return None


def _process_log_in_background(
    record_id,
    request_id: str,
    logs_subdir: str,
    extracted_root: str,
    s3_base_path: str,
):
    """
    Background task: run LLM summarization, store/upload summary, update record.
    Runs in a thread pool executor so the uvicorn event loop is never blocked.

    For INTERNAL_LOGSENSE:
      - Summary is saved to {SAVE_ROOT}/{request_id}/summary.txt
      - status.json is updated at each stage
      - Extracted files are NOT cleaned up (kept for reference)

    For non-INTERNAL_LOGSENSE:
      - Summary is uploaded to S3
      - Portal logsense record is updated via API
      - extracted_root is cleaned up after completion
    """
    log.info(f"[{request_id}] Background processing started")

    try:
        # Step 1: Mark as PROCESSING
        _update_logsense_record(record_id, {
            "status": "PROCESSING",
            "processing_started_at": datetime.utcnow().isoformat(),
        })
        log.info(f"[{request_id}] Marked as PROCESSING")

        # Step 2: Run LLM summarization (the slow part)
        try:
            summary = run_log_summarization(logs_subdir, MODEL="None")
            log.info(f"[{request_id}] LLM summarization completed")
        except Exception as e:
            raise RuntimeError(f"LLM summarization failed: {str(e)}")

        if not summary:
            raise RuntimeError("LLM summarization returned empty result")

        if INTERNAL_LOGSENSE:
            # Step 3 (INTERNAL): Save summary to {SAVE_ROOT}/{request_id}/summary.txt
            job_dir = _get_internal_job_dir(request_id)
            summary_path = os.path.join(job_dir, "summary.txt")
            try:
                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(summary)
                log.info(f"[{request_id}] Summary saved to {summary_path}")
            except Exception as e:
                raise RuntimeError(f"Failed to write summary file: {str(e)}")

            # Step 4 (INTERNAL): Mark as COMPLETED with summary path
            _update_logsense_record(record_id, {
                "status": "COMPLETED",
                "summary_path": summary_path,
                "output_file_size_bytes": len(summary.encode("utf-8")),
                "processing_completed_at": datetime.utcnow().isoformat(),
            })
            log.info(f"[{request_id}] Marked as COMPLETED, summary at {summary_path}")

        else:
            # Step 3: Write summary to file in extracted_root
            summary_path = os.path.join(extracted_root, "log_summarization.txt")
            try:
                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(summary)
            except Exception as e:
                raise RuntimeError(f"Failed to write summary file: {str(e)}")

            # Step 4: Upload summary to S3
            s3_summary_key = f"{s3_base_path}/log_summarization.txt"
            s3_result = _upload_to_s3(summary_path, s3_summary_key)

            if not s3_result.get("uploaded"):
                raise RuntimeError(f"Summary S3 upload failed: {s3_result.get('reason', 'unknown')}")

            output_s3_uri = s3_result.get("s3_url")
            try:
                output_file_size_bytes = os.path.getsize(summary_path)
            except Exception:
                output_file_size_bytes = 0

            log.info(f"[{request_id}] Summary uploaded to S3: {output_s3_uri}")

            # Step 5: Mark as COMPLETED
            _update_logsense_record(record_id, {
                "status": "COMPLETED",
                "output_s3_uri": output_s3_uri,
                "output_file_size_bytes": output_file_size_bytes,
                "processing_completed_at": datetime.utcnow().isoformat(),
            })
            log.info(f"[{request_id}] Marked as COMPLETED")

    except Exception as e:
        log.error(f"[{request_id}] Background processing failed: {str(e)}")
        try:
            _update_logsense_record(record_id, {
                "status": "FAILED",
                "error_message": str(e)[:500],
                "processing_completed_at": datetime.utcnow().isoformat(),
            })
            log.info(f"[{request_id}] Marked as FAILED")
        except Exception as update_err:
            log.error(f"[{request_id}] Failed to mark record as FAILED: {str(update_err)}")

    finally:
        # For non-INTERNAL_LOGSENSE, clean up the extracted directory
        if not INTERNAL_LOGSENSE:
            try:
                if os.path.exists(extracted_root):
                    shutil.rmtree(extracted_root, ignore_errors=True)
                log.info(f"[{request_id}] Cleaned up extracted_root: {extracted_root}")
            except Exception as e:
                log.warning(f"[{request_id}] Failed to clean up extracted_root: {str(e)}")


@app.get("/health")
def health():
    return {"status": "ok"}


class ServiceabilityRequest(BaseModel):
    s3_upload_path: str
    database_row_id: str


def _process_serviceability_in_background(
    bucket_name: str, s3_key: str, database_row_id: str, s3_upload_path: str
):
    """
    Background worker for the /api/v1/serviceability endpoint.
    Downloads files from S3, runs the fw_assert pipeline, and POSTs the
    result to INCIDENT_SERVICE (which handles S3 upload and DB update).
    """
    import datetime
    import hashlib
    import hmac as _hmac
    import xml.etree.ElementTree as ET
    from urllib.parse import quote

    tmp_dir = None
    try:
        region = os.getenv("AWS_REGION", "us-east-1")
        s3_endpoint_url = os.getenv("S3_ENDPOINT_URL") or None
        s3_client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=s3_endpoint_url,
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            config=Config(
                retries={"max_attempts": 6, "mode": "adaptive"},
                read_timeout=300,
                connect_timeout=10,
            ),
        )

        job_id = uuid.uuid4().hex[:8]
        tmp_dir = os.path.join("/tmp", f"fw_assert_{job_id}")
        os.makedirs(tmp_dir, exist_ok=True)

        prefix = s3_key.rstrip("/") + "/"

        def _s3_list_keys(pfx):
            access_key = os.getenv("S3_ACCESS_KEY_ID", "")
            secret_key = os.getenv("S3_SECRET_ACCESS_KEY", "")
            aws_region = os.getenv("AWS_REGION", "us-east-1")
            host = s3_endpoint_url.replace("http://", "").replace("https://", "")
            scheme = "https" if s3_endpoint_url.startswith("https") else "http"

            now = datetime.datetime.utcnow()
            amz_date = now.strftime("%Y%m%dT%H%M%SZ")
            date_stamp = now.strftime("%Y%m%d")

            encoded_prefix = quote(pfx, safe="")
            canonical_qs = f"prefix={encoded_prefix}"
            canonical_uri = f"/{bucket_name}"
            payload_hash = hashlib.sha256(b"").hexdigest()
            canonical_headers = f"host:{host}\nx-amz-date:{amz_date}\n"
            signed_headers = "host;x-amz-date"
            canonical_request = "\n".join([
                "GET", canonical_uri, canonical_qs,
                canonical_headers, signed_headers, payload_hash
            ])
            credential_scope = f"{date_stamp}/{aws_region}/s3/aws4_request"
            string_to_sign = "\n".join([
                "AWS4-HMAC-SHA256", amz_date, credential_scope,
                hashlib.sha256(canonical_request.encode()).hexdigest()
            ])

            def _sign(key, msg):
                return _hmac.new(key, msg.encode(), hashlib.sha256).digest()

            signing_key = _sign(
                _sign(_sign(_sign(f"AWS4{secret_key}".encode(), date_stamp), aws_region), "s3"),
                "aws4_request"
            )
            signature = _hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
            auth_header = (
                f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
                f"SignedHeaders={signed_headers}, Signature={signature}"
            )

            list_url = f"{scheme}://{host}/{bucket_name}?prefix={pfx}"
            resp = requests.get(list_url, headers={
                "x-amz-date": amz_date,
                "x-amz-content-sha256": payload_hash,
                "Authorization": auth_header,
            }, timeout=300)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
            keys = [el.text for el in root.findall(".//s3:Key", ns) if el.text]
            if not keys:
                keys = [el.text for el in root.findall(".//Key") if el.text]
            return keys

        # ---- Download all files from S3 prefix ----
        all_keys = []
        try:
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    all_keys = _s3_list_keys(prefix)
                    break
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait = 2 ** attempt
                    log.warning(f"S3 listing attempt {attempt+1} failed ({e}), retrying in {wait}s")
                    time.sleep(wait)
            log.info(f"Listed {len(all_keys)} objects under prefix {prefix}: {all_keys}")
        except Exception as e:
            log.warning(f"S3 listing failed ({e}), will probe for tar via list_objects")

        for key in all_keys:
            filename = os.path.basename(key)
            if not filename:
                continue
            dest = os.path.join(tmp_dir, filename)
            try:
                log.info(f"Downloading {key} -> {dest}")
                s3_client.download_file(bucket_name, key, dest)
            except ClientError as e:
                log.warning(f"Skipping {key}: {e}")

        # ---- Determine incident type from JSON metadata ----
        incident_type = None
        for fname in os.listdir(tmp_dir):
            if fname.endswith(".json"):
                json_path = os.path.join(tmp_dir, fname)
                try:
                    with open(json_path) as jf:
                        metadata = json.load(jf)
                    raw_type = metadata.get("incident_type")
                    incident_type = raw_type.upper() if raw_type else None
                    log.info(f"Incident metadata: incident_type={incident_type}")
                except Exception as e:
                    log.warning(f"Failed to parse {fname}: {e}")
                break
        log.info(f"Resolved incident_type: {incident_type}")

        # ---- Find the incident tar ----
        local_tar_path = None
        for fname in os.listdir(tmp_dir):
            if fname.startswith("incident_") and fname.endswith(".tar"):
                local_tar_path = os.path.join(tmp_dir, fname)
                log.info(f"Found incident tar in tmp_dir: {local_tar_path}")
                break

        if local_tar_path is None:
            log.info("No tar found via listing, probing S3 with list_objects fallback")
            try:
                paginator = s3_client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                    for obj in page.get("Contents", []):
                        key = obj["Key"]
                        fname = os.path.basename(key)
                        if not fname:
                            continue
                        if fname.startswith("incident_") and fname.endswith(".tar"):
                            dest = os.path.join(tmp_dir, fname)
                            s3_client.download_file(bucket_name, key, dest)
                            local_tar_path = dest
                            log.info(f"Downloaded tar via list_objects fallback: {dest}")
                        elif fname.endswith(".json"):
                            dest = os.path.join(tmp_dir, fname)
                            s3_client.download_file(bucket_name, key, dest)
                            log.info(f"Downloaded JSON via list_objects fallback: {dest}")
            except Exception as e:
                log.warning(f"list_objects fallback also failed: {e}")

        # ---- Re-check incident type if JSON was downloaded in fallback ----
        if incident_type is None:
            for fname in os.listdir(tmp_dir):
                if fname.endswith(".json"):
                    json_path = os.path.join(tmp_dir, fname)
                    try:
                        with open(json_path) as jf:
                            metadata = json.load(jf)
                        new_type = metadata.get("incident_type")
                        if new_type:
                            incident_type = new_type.upper()
                            log.info(f"Updated incident_type from fallback JSON: {incident_type}")
                    except Exception:
                        pass
                    break

        if incident_type is None:
            log.error("incident_type could not be determined: no JSON metadata found or incident_type key missing")
            _notify_incident_service(database_row_id, s3_upload_path, None, "failure")
            return

        if local_tar_path is None or not os.path.exists(local_tar_path):
            log.error(f"No incident tar file found under S3 prefix: {prefix}")
            _notify_incident_service(database_row_id, s3_upload_path, None, "failure")
            return

        # ---- Extract all tar contents, recursing into nested tars ----
        extract_dir = os.path.join(tmp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        def _extract_tar_recursive(tar_path, dest_dir):
            """Extract a tar (or tar.gz/tgz) into dest_dir, then recurse
            into any nested tar/tar.gz/tgz files found inside."""
            with tarfile.open(tar_path, mode="r:*") as tar:
                members = tar.getmembers()
                log.info(f"Tar contents ({tar_path}): {[m.name for m in members]}")
                _validate_tar_members(tar, MAX_EXTRACT_BYTES)
                tar.extractall(path=dest_dir)

            # Now check for nested tar files and extract them too
            for root_dir, dirs, files in os.walk(dest_dir):
                for fname in files:
                    fpath = os.path.join(root_dir, fname)
                    if fname.endswith((".tar", ".tar.gz", ".tgz")):
                        log.info(f"Found nested tar: {fpath}, extracting...")
                        nested_dir = os.path.join(root_dir, fname + "_extracted")
                        os.makedirs(nested_dir, exist_ok=True)
                        try:
                            _extract_tar_recursive(fpath, nested_dir)
                        except Exception as e:
                            log.warning(f"Failed to extract nested tar {fpath}: {e}")

        _extract_tar_recursive(local_tar_path, extract_dir)

        if incident_type == "KFENCE":
            # ---- KFENCE pipeline: find syslog file (syslog.txt or syslog.log) ----
            syslog_path = None
            for root_dir, dirs, files in os.walk(extract_dir):
                for fname in files:
                    if fname in ("syslog.txt", "syslog.log") and syslog_path is None:
                        syslog_path = os.path.join(root_dir, fname)
                        log.info(f"Found syslog at {syslog_path}")
                if syslog_path:
                    break

            if syslog_path is None:
                log.error("Required syslog file not found for KFENCE incident")
                _notify_incident_service(database_row_id, s3_upload_path, None, "failure")
                return

            # ---- Run KFENCE pipeline ----
            log.info(f"Running kfence pipeline on {syslog_path}")
            summary = run_kfence_pipeline(syslog_path=syslog_path)
            log.info("kfence pipeline complete")

        elif incident_type == "FLUSH_52_CRITICAL":
            # ---- FLUSH_52_CRITICAL pipeline: find required and optional log files ----
            logread_path = None
            cnss_diag_path = None
            anomaly_master_path = ""
            flush52_details_path = ""
            wifistats_path = ""

            for root_dir, dirs, files in os.walk(extract_dir):
                for fname in files:
                    fpath = os.path.join(root_dir, fname)
                    if fname == "logread_output.txt" and logread_path is None:
                        logread_path = fpath
                        log.info(f"Found logread_output.txt at {logread_path}")
                    elif fname == "default_cnss_diag.txt" and cnss_diag_path is None:
                        cnss_diag_path = fpath
                        log.info(f"Found default_cnss_diag.txt at {cnss_diag_path}")
                    elif fname == "anomaly_master.log" and not anomaly_master_path:
                        anomaly_master_path = fpath
                        log.info(f"Found anomaly_master.log at {anomaly_master_path}")
                    elif fname == "flush_52_details.txt" and not flush52_details_path:
                        flush52_details_path = fpath
                        log.info(f"Found flush_52_details.txt at {flush52_details_path}")
                    elif fname.startswith("wifistats") and fname.endswith(".txt") and not wifistats_path:
                        wifistats_path = fpath
                        log.info(f"Found wifistats file at {wifistats_path}")

            if logread_path is None or cnss_diag_path is None:
                log.error(
                    f"Required log files not found for FLUSH_52_CRITICAL incident. "
                    f"logread_output.txt={'found' if logread_path else 'MISSING'}, "
                    f"default_cnss_diag.txt={'found' if cnss_diag_path else 'MISSING'}"
                )
                _notify_incident_service(database_row_id, s3_upload_path, None, "failure")
                return

            # ---- Run FLUSH_52_CRITICAL pipeline ----
            log.info(f"Running flush52 pipeline on {extract_dir}")
            summary = run_flush52_pipeline(
                logread_path=logread_path,
                cnss_diag_path=cnss_diag_path,
                anomaly_master_path=anomaly_master_path,
                flush52_details_path=flush52_details_path,
                wifistats_path=wifistats_path,
            )
            log.info("flush52 pipeline complete")

        elif incident_type == "FW_ASSERT":
            # ---- FW_ASSERT pipeline: find logread_output.txt and default_cnss_diag.txt ----
            syslog_path = None
            cnss_diag_path = None
            for root_dir, dirs, files in os.walk(extract_dir):
                for fname in files:
                    if fname == "logread_output.txt" and syslog_path is None:
                        syslog_path = os.path.join(root_dir, fname)
                        log.info(f"Found logread_output.txt at {syslog_path}")
                    elif fname == "default_cnss_diag.txt" and cnss_diag_path is None:
                        cnss_diag_path = os.path.join(root_dir, fname)
                        log.info(f"Found default_cnss_diag.txt at {cnss_diag_path}")
                if syslog_path and cnss_diag_path:
                    break

            if syslog_path is None or cnss_diag_path is None:
                log.error(
                    f"Required log files not found after recursive extraction. "
                    f"logread_output.txt={'found' if syslog_path else 'MISSING'}, "
                    f"default_cnss_diag.txt={'found' if cnss_diag_path else 'MISSING'}"
                )
                _notify_incident_service(database_row_id, s3_upload_path, None, "failure")
                return

            # ---- Run FW_ASSERT pipeline ----
            log.info(f"Running fw_assert pipeline on {extract_dir}")
            summary = run_fw_assert_pipeline(
                syslog_path=syslog_path,
                cnss_diag_path=cnss_diag_path,
            )
            log.info("fw_assert pipeline complete")

        elif incident_type == "CONNECTIVITY":
            # ---- CONNECTIVITY pipeline: find directory containing fd_logs ----
            connectivity_dir = None
            for root_dir, dirs, files in os.walk(extract_dir):
                for fname in files:
                    if fname.endswith("fd_logs.txt"):
                        connectivity_dir = root_dir
                        log.info(f"Found connectivity fd_logs file at {os.path.join(root_dir, fname)}")
                        break
                if connectivity_dir:
                    break

            if connectivity_dir is None:
                log.error("Required fd_logs.txt file not found for CONNECTIVITY incident")
                _notify_incident_service(database_row_id, s3_upload_path, None, "failure")
                return

            # ---- Run CONNECTIVITY pipeline ----
            log.info(f"Running connectivity pipeline on {connectivity_dir}")
            summary = run_log_summarization(connectivity_dir, MODEL="None")
            log.info("connectivity pipeline complete")

        else:
            log.error(f"Unrecognized incident_type: {incident_type}")
            _notify_incident_service(database_row_id, s3_upload_path, None, "failure")
            return

        # ---- Notify INCIDENT_SERVICE: success ----
        _notify_incident_service(database_row_id, s3_upload_path, summary, "completed")
        log.info(f"Serviceability background task completed successfully for row_id={database_row_id}")

    except Exception as e:
        log.error(f"Serviceability background task failed for row_id={database_row_id}: {e}")
        try:
            _notify_incident_service(database_row_id, s3_upload_path, None, "failure")
        except Exception as notify_err:
            log.error(f"Failed to notify INCIDENT_SERVICE on error: {notify_err}")
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _notify_incident_service(
    database_row_id: str, s3_upload_path: str, summary, status: str
):
    """POST the summarization result to the INCIDENT_SERVICE endpoint."""
    incident_url = os.getenv("INCIDENT_SERVICE", "")
    if not incident_url:
        log.warning("INCIDENT_SERVICE not configured, skipping notification")
        return

    payload = {
        "database_row_id": database_row_id,
        "s3_upload_path": s3_upload_path,
        "summary": summary if summary is not None else "",
        "summary_status": status,
    }
    try:
        resp = requests.post(incident_url, json=payload, timeout=30)
        resp.raise_for_status()
        log.info(f"INCIDENT_SERVICE notified: row_id={database_row_id}, status={status}, HTTP {resp.status_code}")
    except Exception as e:
        log.error(f"Failed to notify INCIDENT_SERVICE (row_id={database_row_id}): {e}")


@app.post("/api/v1/serviceability", status_code=202)
async def analyze_fw_assert(
    body: ServiceabilityRequest,
    token_payload: dict = Depends(verify_jwt_token)
):
    """
    Analyze a firmware assert from a tar file stored in S3.

    Accepts the request, validates the S3 path, and immediately returns 202.
    The actual download, extraction, summarization, S3 upload, and DB update
    run asynchronously in a background thread.
    """
    s3_upload_path = body.s3_upload_path
    database_row_id = body.database_row_id
    log.info(f"Serviceability request received for S3 path: {s3_upload_path}, row_id: {database_row_id}")

    # ------------------------------------------------------------------
    # Step 1: Parse S3 path — expects a key-only path:
    #   path/to/uuid
    # Also accepts s3://bucket/path/to/uuid — the scheme and bucket are
    # stripped and the bucket is always resolved from S3_BUCKET_NAME.
    # ------------------------------------------------------------------
    bucket_name = os.getenv("S3_BUCKET_NAME", "")
    if not bucket_name:
        raise HTTPException(
            status_code=500,
            detail="S3_BUCKET_NAME is not configured in the environment"
        )

    # Strip s3:// scheme if present, then strip the bucket prefix if it matches
    path = s3_upload_path
    if path.startswith("s3://"):
        path = path[len("s3://"):]
        # Remove the bucket segment (everything up to the first slash)
        slash_idx = path.find("/")
        if slash_idx != -1:
            path = path[slash_idx + 1:]

    s3_key = path.strip("/")
    if not s3_key:
        raise HTTPException(
            status_code=400,
            detail="s3_upload_path must be a non-empty key path (e.g. path/to/file.tar)"
        )

    log.info(f"Parsed S3 bucket={bucket_name}, key={s3_key}")

    # Fire background task
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,
        _process_serviceability_in_background,
        bucket_name,
        s3_key,
        database_row_id,
        s3_upload_path,
    )
    log.info(f"Background serviceability task fired for row_id={database_row_id}")

    return JSONResponse(
        status_code=202,
        content={
            "message": "Serviceability request received and queued for analysis",
            "database_row_id": database_row_id,
            "s3_key": s3_key,
            "status": "pending",
        }
    )


@app.post("/api/v1/connectivity", status_code=202)
async def submit_log_for_analysis(
    file: UploadFile = File(...),
    token_payload: dict = Depends(verify_jwt_token)
):
    """
    Receive a tar file, validate it, and queue it for LLM analysis.

    For INTERNAL_LOGSENSE mode:
      - Generates a unique request_id immediately
      - Creates {SAVE_ROOT}/{request_id}/ directory
      - Saves the TAR file to {SAVE_ROOT}/{request_id}/upload.tar
      - Extracts TAR to {SAVE_ROOT}/{request_id}/extracted/
      - Writes initial status.json with PENDING status
      - Returns request_id in the response

    For non-INTERNAL_LOGSENSE mode:
      - Validates JWT, checks portal API limits, uploads to S3
      - Creates a portal logsense record and returns its request_id

    Poll GET /api/v1/connectivity/{request_id} to check status and retrieve the report.
    """
    # Step 1: Extract device UUID from JWT token (uid field)
    device_uuid = token_payload.get("uid")
    if not device_uuid and not INTERNAL_LOGSENSE:
        log.error("uid (device UUID) not found in JWT token payload")
        raise HTTPException(
            status_code=400,
            detail="Device UUID not found in token"
        )

    # Step 2: Get device info from portal API (mocked for INTERNAL_LOGSENSE)
    device_info = _get_device_info(device_uuid)
    oem_id = device_info.get("oem_id")
    serial_number = device_info.get("serial_number")

    if not oem_id:
        log.error("oem_id not found in device info")
        raise HTTPException(status_code=500, detail="oem_id not found in device info")

    if not serial_number:
        log.warning("serial_number not found in device info, using device_uuid as fallback")
        serial_number = device_uuid

    # Step 3: Check API limit (mocked for INTERNAL_LOGSENSE)
    api_limit_info = _check_api_limit(oem_id)
    log.info(f"API limit check result: {api_limit_info}")

    # Step 4: Read and validate the tar file
    contents = await file.read()
    log.info(f"Received file: {file.filename}, size: {len(contents)} bytes")

    tar_file = BytesIO(contents)

    try:
        tar_file.seek(0)
        with tarfile.open(fileobj=tar_file, mode="r:*") as t:
            _validate_tar_members(t, MAX_EXTRACT_BYTES)
        tar_file.seek(0)
    except tarfile.TarError:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid tar archive.")
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Validation failed")
        raise HTTPException(status_code=400, detail=f"Failed to validate archive: {str(e)}")

    # -----------------------------------------------------------------------
    # INTERNAL_LOGSENSE path: disk-based job directory
    # -----------------------------------------------------------------------
    if INTERNAL_LOGSENSE:
        # Generate request_id and create job directory immediately
        request_id = str(uuid.uuid4())
        job_dir = _get_internal_job_dir(request_id)
        os.makedirs(job_dir, exist_ok=True)
        log.info(f"[{request_id}] Created job directory: {job_dir}")

        # Save TAR file to job directory
        tar_filename = file.filename or "upload.tar"
        tar_save_path = os.path.join(job_dir, tar_filename)
        try:
            tar_file.seek(0)
            with open(tar_save_path, "wb") as f:
                f.write(tar_file.read())
            log.info(f"[{request_id}] TAR file saved to {tar_save_path}")
        except Exception as e:
            log.warning(f"[{request_id}] Failed to save TAR file: {str(e)}")

        # Extract TAR to job_dir/extracted/
        extracted_subdir = os.path.join(job_dir, "extracted")
        os.makedirs(extracted_subdir, exist_ok=True)
        log.info(f"[{request_id}] Extracting TAR to {extracted_subdir}")

        try:
            tar_file.seek(0)
            with tarfile.open(fileobj=tar_file, mode="r:*") as t:
                _safe_extractall(t, extracted_subdir)
            log.info(f"[{request_id}] TAR extracted to {extracted_subdir}")
        except HTTPException:
            raise
        except Exception as e:
            log.exception("Extraction failed")
            raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

        extracted_root = _detect_extracted_root(extracted_subdir)

        # Set write permissions
        try:
            for root, dirs, files in os.walk(extracted_root):
                os.chmod(root, 0o777)
                for filename in files:
                    os.chmod(os.path.join(root, filename), 0o666)
        except Exception as e:
            log.warning(f"[{request_id}] Failed to set permissions: {str(e)}")

        try:
            top_level = sorted(os.listdir(extracted_root))
        except Exception:
            top_level = []

        # Write initial status.json
        _write_internal_job(request_id, {
            "record_id": request_id,
            "request_id": request_id,
            "status": "PENDING",
            "tar_path": tar_save_path,
            "extracted_path": extracted_root,
            "summary_path": None,
            "output_file_size_bytes": None,
            "error_message": None,
            "created_at": datetime.utcnow().isoformat(),
            "processing_started_at": None,
            "processing_completed_at": None,
        })
        log.info(f"[{request_id}] status.json written with PENDING status")

        # Fire background task (logs_subdir = extracted_root, no copy needed)
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            _process_log_in_background,
            request_id,       # record_id == request_id for INTERNAL_LOGSENSE
            request_id,
            extracted_root,   # logs_subdir
            extracted_root,   # extracted_root
            None,             # s3_base_path not used in INTERNAL_LOGSENSE
        )
        log.info(f"[{request_id}] Background processing task fired")

        return JSONResponse(
            status_code=202,
            content={
                "message": "Log file received and queued for analysis",
                "request_id": request_id,
                "status": "pending",
                "top_level_entries": top_level[:200],
            }
        )

    # -----------------------------------------------------------------------
    # Non-INTERNAL_LOGSENSE path: portal backend + S3
    # -----------------------------------------------------------------------

    # Step 5: Extract tar to disk
    dest_dir = _make_upload_dir("upload.tar")
    log.info("Tar File Received -> extracting to mounted volume %s", dest_dir)

    try:
        tar_file.seek(0)
        with tarfile.open(fileobj=tar_file, mode="r:*") as t:
            _safe_extractall(t, dest_dir)
            log.info("Tar File successfully extracted to mounted volume %s", dest_dir)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Extraction failed")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

    extracted_root = _detect_extracted_root(dest_dir)

    # Set write permissions
    try:
        for root, dirs, files in os.walk(extracted_root):
            os.chmod(root, 0o777)
            for filename in files:
                os.chmod(os.path.join(root, filename), 0o666)
    except Exception as e:
        log.warning(f"Failed to set permissions on extracted_root: {str(e)}")

    try:
        top_level = sorted(os.listdir(extracted_root))
    except Exception:
        top_level = []

    # Step 6: Copy to logs directory (used by LLM triage)
    logs_dir = os.path.join(SAVE_ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    logs_subdir = os.path.join(logs_dir, os.path.basename(extracted_root))

    try:
        if os.path.exists(logs_subdir):
            shutil.rmtree(logs_subdir)
        shutil.copytree(extracted_root, logs_subdir)
        for root, dirs, files in os.walk(logs_subdir):
            os.chmod(root, 0o777)
            for filename in files:
                os.chmod(os.path.join(root, filename), 0o666)
        log.info(f"Copied extracted contents to logs directory: {logs_subdir}")
    except Exception as e:
        log.exception("Failed to copy extracted contents to logs directory")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to copy extracted contents to logs directory: {str(e)}"
        )

    # Step 7: Upload tar to S3 synchronously (required before creating logsense record)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    s3_base_path = f"{oem_id}/{serial_number}/{ts}"
    tar_filename = file.filename or "upload.tar"
    tar_save_path = os.path.join(dest_dir, tar_filename)
    input_s3_uri = None

    try:
        with open(tar_save_path, "wb") as f:
            tar_file.seek(0)
            f.write(tar_file.read())
        s3_tar_key = f"{s3_base_path}/{tar_filename}"
        s3_tar_result = _upload_to_s3(tar_save_path, s3_tar_key)
        if s3_tar_result.get("uploaded"):
            input_s3_uri = s3_tar_result.get("s3_url")
            log.info(f"Tar file uploaded to S3: {input_s3_uri}")
        else:
            log.warning(f"Tar S3 upload failed: {s3_tar_result.get('reason')}")
    except Exception as e:
        log.warning(f"Failed to save/upload tar file to S3: {str(e)}")

    # Step 8: Create logsense record with PENDING status
    device_id = device_info.get("id")
    logsense_record_id = None
    request_id = None

    if device_id and input_s3_uri:
        logsense_result = _create_logsense_record(
            device_id=device_id,
            input_s3_uri=input_s3_uri,
            file_size_bytes=len(contents),
        )
        if logsense_result.get("created"):
            logsense_record_id = logsense_result.get("id")
            request_id = logsense_result.get("request_id")
            log.info(f"Created logsense record: id={logsense_record_id}, request_id={request_id}")
        else:
            log.warning(f"Failed to create logsense record: {logsense_result.get('reason')}")
    else:
        log.warning("Cannot create logsense record: device_id or input_s3_uri missing")

    # Step 9: Fire background task for LLM processing
    if logsense_record_id is not None:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            None,
            _process_log_in_background,
            logsense_record_id,
            request_id,
            logs_subdir,
            extracted_root,
            s3_base_path,
        )
        log.info(f"Background processing task fired for request_id={request_id}")
    else:
        log.warning("No logsense record created; background task not started")

    return JSONResponse(
        status_code=202,
        content={
            "message": "Log file received and queued for analysis",
            "request_id": request_id,
            "status": "pending",
            "top_level_entries": top_level[:200],
        }
    )


@app.get("/api/v1/connectivity/{request_id}")
async def get_log_analysis_status(
    request_id: str,
    token_payload: dict = Depends(verify_jwt_token)
):
    """
    Poll the status of a log analysis request.

    For INTERNAL_LOGSENSE mode:
      - Reads status from {SAVE_ROOT}/{request_id}/status.json
      - When status is 'completed', returns the full summary text in the response

    For non-INTERNAL_LOGSENSE mode:
      - Queries the portal backend for the logsense record
      - Returns output_s3_uri / presigned URL when completed
    """
    record = _get_logsense_record_by_request_id(request_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Request ID '{request_id}' not found"
        )

    status_value = record.get("status", "unknown")
    status_lower = status_value.lower() if status_value else "unknown"

    response = {
        "request_id": record.get("request_id", request_id),
        "status": status_lower,
        "created_at": record.get("created_at"),
        "processing_started_at": record.get("processing_started_at"),
        "processing_completed_at": record.get("processing_completed_at"),
        "error_message": record.get("error_message"),
        "output_file_size_bytes": record.get("output_file_size_bytes"),
    }

    if INTERNAL_LOGSENSE:
        # For internal mode, return the actual summary text when completed
        if status_lower == "completed":
            summary_path = record.get("summary_path")
            summary_text = None
            if summary_path and os.path.exists(summary_path):
                try:
                    with open(summary_path, encoding="utf-8") as f:
                        summary_text = f.read()
                    log.info(f"[{request_id}] Returning summary from {summary_path}")
                except Exception as e:
                    log.error(f"[{request_id}] Failed to read summary file: {str(e)}")
            response["summary"] = summary_text
            response["summary_path"] = summary_path
        else:
            response["summary"] = None
    else:
        # For portal-backed mode, return S3 URIs
        response["output_s3_uri"] = record.get("output_s3_uri")
        response["output_s3_presigned_url"] = record.get("output_s3_presigned_url")
        response["device_serial_number"] = record.get("device_serial_number")
        response["file_size_bytes"] = record.get("file_size_bytes")

    return response

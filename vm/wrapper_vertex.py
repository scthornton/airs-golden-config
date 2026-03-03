#!/usr/bin/env python3
"""
Golden Config — OpenAI + AIRS Hard-Blocking Wrapper

Architecture:
  1. Receive prompt (OpenAI-compat format)
  2. AIRS Scan API → prompt scan
  3. If AIRS blocks → return blocked message (LLM never sees it)
  4. OpenAI API → generate response
  5. AIRS Scan API → response scan
  6. If AIRS blocks response → return sanitized message
  7. Return clean response

Key difference from airs_claude_wrapper.py:
  - That wrapper passes prompts to Claude regardless (observe mode, line 79)
  - THIS wrapper hard-blocks on AIRS verdict — attack prompts never reach the LLM
"""

from flask import Flask, request, jsonify
import requests
import os
import uuid
import time
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("golden-config")

# ── Configuration ──────────────────────────────────────────────────────────────
AIRS_API_URL = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"
PANW_API_KEY = os.getenv("PANW_AI_SEC_API_KEY")
SECURITY_PROFILE = os.getenv("PRISMA_AIRS_PROFILE", "redteamtest")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

BLOCKED_MESSAGE = (
    "I'm unable to process this request. "
    "It has been flagged by our security system."
)
RESPONSE_BLOCKED_MESSAGE = (
    "The response was blocked by our security system for policy reasons."
)


# ── AIRS Scanning ──────────────────────────────────────────────────────────────

def airs_scan_prompt(prompt: str, tr_id: str) -> dict | None:
    """Scan a prompt through AIRS. Returns response dict or None on error."""
    if not PANW_API_KEY:
        log.warning("PANW_AI_SEC_API_KEY not set — skipping scan")
        return None

    payload = {
        "tr_id": tr_id,
        "ai_profile": {"profile_name": SECURITY_PROFILE},
        "metadata": {
            "app_user": "red-team-target",
            "ai_model": DEFAULT_MODEL,
        },
        "contents": [{"prompt": prompt}],
    }

    try:
        resp = requests.post(
            AIRS_API_URL,
            headers={
                "X-Pan-Token": PANW_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if resp.status_code == 200:
            result = resp.json()
            log.info(
                "AIRS prompt scan: action=%s category=%s detections=%s",
                result.get("action"),
                result.get("category"),
                result.get("prompt_detected", {}),
            )
            return result
        else:
            log.error("AIRS scan HTTP %d: %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        log.error("AIRS scan error: %s", e)
        return None


def airs_scan_response(prompt: str, response_text: str, tr_id: str) -> dict | None:
    """Scan a response through AIRS. Returns response dict or None on error."""
    if not PANW_API_KEY:
        return None

    payload = {
        "tr_id": tr_id,
        "ai_profile": {"profile_name": SECURITY_PROFILE},
        "metadata": {
            "app_user": "red-team-target",
            "ai_model": DEFAULT_MODEL,
        },
        "contents": [{"prompt": prompt, "response": response_text}],
    }

    try:
        resp = requests.post(
            AIRS_API_URL,
            headers={
                "X-Pan-Token": PANW_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if resp.status_code == 200:
            result = resp.json()
            log.info(
                "AIRS response scan: action=%s category=%s",
                result.get("action"),
                result.get("category"),
            )
            return result
        else:
            log.error("AIRS response scan HTTP %d: %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        log.error("AIRS response scan error: %s", e)
        return None


# ── OpenAI-compat response builder ────────────────────────────────────────────

def make_response(content: str, model: str = None, usage: dict = None, airs_meta: dict = None):
    """Build an OpenAI-format chat completion response."""
    resp = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:20]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model or DEFAULT_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
    if airs_meta:
        resp["airs_runtime"] = airs_meta
    return resp


def extract_airs_meta(airs_result: dict) -> dict:
    """Extract AIRS metadata for response annotation."""
    return {
        "action": airs_result.get("action"),
        "category": airs_result.get("category"),
        "prompt_detected": airs_result.get("prompt_detected", {}),
        "response_detected": airs_result.get("response_detected", {}),
        "scan_id": airs_result.get("scan_id"),
        "report_id": airs_result.get("report_id"),
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    data = request.json or {}
    messages = data.get("messages", [])
    max_tokens = data.get("max_tokens", 1024)

    if not messages:
        return jsonify({"error": "messages array is required"}), 400

    # Extract the last user prompt for scanning
    user_prompt = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_prompt = msg.get("content", "")
            break

    tr_id = str(uuid.uuid4())

    # ── Step 1: AIRS Prompt Scan ──────────────────────────────────────
    airs_prompt_result = airs_scan_prompt(user_prompt, tr_id)

    if airs_prompt_result and airs_prompt_result.get("action") == "block":
        log.info("BLOCKED prompt: %s...", user_prompt[:80])
        meta = extract_airs_meta(airs_prompt_result)
        meta["blocked_stage"] = "prompt"
        return jsonify(make_response(BLOCKED_MESSAGE, airs_meta=meta)), 200

    # ── Step 2: OpenAI API ────────────────────────────────────────────
    if not OPENAI_API_KEY:
        return jsonify({"error": "OPENAI_API_KEY not set"}), 500

    try:
        openai_payload = {
            "model": data.get("model", DEFAULT_MODEL),
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if data.get("temperature") is not None:
            openai_payload["temperature"] = data["temperature"]

        openai_resp = requests.post(
            OPENAI_API_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=openai_payload,
            timeout=60,
        )
        openai_resp.raise_for_status()
        openai_data = openai_resp.json()

        response_text = openai_data["choices"][0]["message"]["content"]
        usage = openai_data.get("usage", {})

    except requests.exceptions.HTTPError:
        log.error("OpenAI API %d: %s", openai_resp.status_code, openai_resp.text[:200])
        return jsonify({"error": f"OpenAI API error: {openai_resp.status_code}"}), 502
    except Exception as e:
        log.error("OpenAI error: %s", e)
        return jsonify({"error": str(e)}), 502

    # ── Step 3: AIRS Response Scan ────────────────────────────────────
    airs_resp_result = airs_scan_response(user_prompt, response_text, tr_id)

    if airs_resp_result and airs_resp_result.get("action") == "block":
        log.info("BLOCKED response for prompt: %s...", user_prompt[:80])
        meta = extract_airs_meta(airs_resp_result)
        meta["blocked_stage"] = "response"
        return jsonify(make_response(RESPONSE_BLOCKED_MESSAGE, airs_meta=meta, usage=usage)), 200

    # ── Step 4: Return clean response ─────────────────────────────────
    meta = extract_airs_meta(airs_resp_result) if airs_resp_result else None
    if meta:
        meta["blocked_stage"] = None

    # Pass through the original OpenAI response, just add AIRS metadata
    if airs_meta := meta:
        openai_data["airs_runtime"] = airs_meta
    return jsonify(openai_data), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "Golden Config — AIRS Hard-Block Wrapper",
        "model": DEFAULT_MODEL,
        "security_profile": SECURITY_PROFILE,
        "airs_api_key_set": bool(PANW_API_KEY),
        "openai_api_key_set": bool(OPENAI_API_KEY),
        "mode": "BLOCKING",
    }), 200


@app.route("/debug", methods=["GET"])
def debug():
    panw_preview = (PANW_API_KEY[:10] + "...") if PANW_API_KEY else "NOT SET"
    openai_preview = (OPENAI_API_KEY[:10] + "...") if OPENAI_API_KEY else "NOT SET"
    return jsonify({
        "panw_api_key": panw_preview,
        "openai_api_key": openai_preview,
        "model": DEFAULT_MODEL,
        "security_profile": SECURITY_PROFILE,
    }), 200


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5008))

    if not PANW_API_KEY:
        log.warning("PANW_AI_SEC_API_KEY not set — AIRS scanning disabled (pass-through mode)")
    else:
        log.info("AIRS scanning ENABLED — profile: %s — mode: HARD-BLOCK", SECURITY_PROFILE)

    if not OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY not set — LLM responses disabled")
    else:
        log.info("OpenAI API ready — model: %s", DEFAULT_MODEL)

    log.info("Starting on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False)

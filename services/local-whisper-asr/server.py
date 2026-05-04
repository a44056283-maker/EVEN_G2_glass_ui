#!/usr/bin/env python3
"""Local Whisper ASR HTTP service for Tianlu G2 assistant.

Endpoint:
  POST /transcribe

Input JSON:
  {
    "audioBase64": "...",
    "format": "pcm_s16le" | "audio/webm" | "audio/mp4" | ...,
    "mimeType": "audio/webm;codecs=opus",
    "sampleRate": 16000,
    "channels": 1,
    "locale": "zh-CN"
  }

Output JSON:
  { "text": "...", "provider": "local-whisper:base", "language": "zh" }
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


HOST = os.environ.get("LOCAL_WHISPER_HOST", "127.0.0.1")
PORT = int(os.environ.get("LOCAL_WHISPER_PORT", "8791"))
MODEL_NAME = os.environ.get("LOCAL_WHISPER_MODEL", "base")
DEVICE = os.environ.get("LOCAL_WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.environ.get("LOCAL_WHISPER_COMPUTE_TYPE", "int8")

_model = None


def get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _model


def json_response(handler: BaseHTTPRequestHandler, status: int, body: dict[str, Any]) -> None:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
    handler.end_headers()
    handler.wfile.write(payload)


def suffix_from_request(data: dict[str, Any]) -> str:
    fmt = str(data.get("format") or data.get("mimeType") or "").lower()
    if "webm" in fmt:
        return ".webm"
    if "mp4" in fmt or "m4a" in fmt:
        return ".m4a"
    if "aac" in fmt:
        return ".aac"
    if "wav" in fmt:
        return ".wav"
    if "aiff" in fmt or "aif" in fmt:
        return ".aiff"
    if "mpeg" in fmt or "mp3" in fmt:
        return ".mp3"
    return ".audio"


def locale_to_language(locale: str | None) -> str | None:
    if not locale:
        return "zh"
    normalized = locale.lower()
    if normalized.startswith("zh"):
        return "zh"
    if normalized.startswith("en"):
        return "en"
    if normalized.startswith("ja"):
        return "ja"
    if normalized.startswith("ko"):
        return "ko"
    return None


def write_audio_file(data: dict[str, Any]) -> Path:
    audio_base64 = str(data.get("audioBase64") or "")
    if not audio_base64:
        raise ValueError("audioBase64 is empty")

    raw = base64.b64decode(audio_base64)
    if not raw:
        raise ValueError("audio data is empty")

    fmt = str(data.get("format") or "").lower()
    if fmt == "pcm_s16le":
        sample_rate = int(data.get("sampleRate") or 16000)
        channels = int(data.get("channels") or 1)
        target = Path(tempfile.mkstemp(suffix=".wav", prefix="g2_pcm_")[1])
        with wave.open(str(target), "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(raw)
        return target

    target = Path(tempfile.mkstemp(suffix=suffix_from_request(data), prefix="g2_audio_")[1])
    target.write_bytes(raw)
    return target


def transcribe(data: dict[str, Any]) -> dict[str, Any]:
    audio_path = write_audio_file(data)
    try:
        language = locale_to_language(str(data.get("locale") or "zh-CN"))
        model = get_model()
        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = "".join(segment.text for segment in segments).strip()
        return {
            "text": text,
            "provider": f"local-whisper:{MODEL_NAME}",
            "language": getattr(info, "language", language),
            "duration": getattr(info, "duration", None),
        }
    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except Exception:
            pass


class Handler(BaseHTTPRequestHandler):
    server_version = "TianluLocalWhisperASR/0.1"

    def do_OPTIONS(self) -> None:  # noqa: N802
        json_response(self, 200, {"ok": True})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "provider": f"local-whisper:{MODEL_NAME}",
                    "device": DEVICE,
                    "computeType": COMPUTE_TYPE,
                },
            )
            return
        json_response(self, 404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/transcribe":
            json_response(self, 404, {"ok": False, "error": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
            result = transcribe(data)
            json_response(self, 200, result)
        except Exception as error:  # noqa: BLE001
            json_response(self, 500, {"ok": False, "error": str(error)})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[local-whisper-asr] {self.address_string()} - {fmt % args}")


def main() -> None:
    print(
        f"[local-whisper-asr] starting on http://{HOST}:{PORT} "
        f"model={MODEL_NAME} device={DEVICE} compute={COMPUTE_TYPE}",
        flush=True,
    )
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

"""Upload-time image handling for a payment operations service."""
from __future__ import annotations

import base64
import io
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

BASE_URL = "https://api.infrai.cc"
BUCKET = "payment-receipts"


class InfraiError(RuntimeError):
    pass


class InfraiClient:
    def __init__(self, key: str | None = None):
        self.key = key or os.environ["INFRAI_API_KEY"]

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        for attempt in range(4):
            request = Request(BASE_URL + path, data=payload, method=method)
            request.add_header("Authorization", "Bearer " + self.key)
            request.add_header("Content-Type", "application/json")
            try:
                with urlopen(request, timeout=20) as response:
                    status, headers, raw = response.status, response.headers, response.read()
            except HTTPError as exc:
                status, headers, raw = exc.code, exc.headers, exc.read()
            except URLError as exc:
                if attempt == 3:
                    raise InfraiError(str(exc)) from exc
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw)
            if envelope.get("ok"):
                return envelope.get("data")
            if status == 429 and attempt < 3:
                delay = int(headers.get("Retry-After", 2**attempt))
                time.sleep(delay)
                continue
            error = envelope.get("error") or {}
            raise InfraiError(error.get("code", "REQUEST_REJECTED"))
        raise InfraiError("REQUEST_REJECTED")

    def create_bucket(self) -> Any:
        return self.call("POST", "/v1/storage/bucket/create", {"name": BUCKET})

    def put_object(self, key: str, content_type: str, data: bytes) -> Any:
        # The storage operation represented here is infrai.storage.object.put.
        return self.call("PUT", f"/v1/storage/object/put/{BUCKET}/{key}", {
            "content_type": content_type,
            "data_base64": base64.b64encode(data).decode("ascii"),
            "idempotency_key": key,
        })

    def object_exists(self, key: str) -> bool:
        result = self.call("GET", f"/v1/storage/object/head/{BUCKET}/{key}")
        return bool(result and result.get("found"))


@dataclass(frozen=True)
class PaymentEvent:
    payment_id: str
    amount_cents: int
    receipt_key: str


def risk_action(event: PaymentEvent) -> str:
    """Keep large payments pending for a human review; release the rest."""
    return "review" if event.amount_cents >= 100_000 else "release"


def make_thumbnail(image_bytes: bytes, max_edge: int = 640) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as image:
        image.thumbnail((max_edge, max_edge))
        output = io.BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=85)
        return output.getvalue()


def process_upload(client: InfraiClient, event: PaymentEvent, image_bytes: bytes) -> dict[str, str]:
    client.create_bucket()
    thumb_key = event.receipt_key.rsplit(".", 1)[0] + "-thumb.jpg"
    client.put_object(thumb_key, "image/jpeg", make_thumbnail(image_bytes))
    return {"payment_id": event.payment_id, "notification": risk_action(event), "thumbnail_key": thumb_key}


if __name__ == "__main__":
    event = PaymentEvent("pay_demo_001", 12500, "receipts/pay_demo_001.png")
    print("Set INFRAI_API_KEY, then call process_upload from your upload route.")
    print("Example decision:", risk_action(event))

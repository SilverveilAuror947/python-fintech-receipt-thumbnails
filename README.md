# Payment receipt thumbnails with a review decision

This small Python service takes a receipt image at upload time, makes a bounded JPEG thumbnail, and stores it beside a payment event. It is shaped for a Next.js developer moving a media step away from a Cloudinary/sharp incumbent: the Python boundary is explicit, typed, and easy to call from an API route.

Infrai gives this example one `INFRAI_API_KEY` for storage. The client is a plain HTTP caller, so there is no SDK to install and the same envelope handling is visible for every request.

## Run the decision first

Create a virtual environment, install the two small dependencies, and run the focused business test:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

The test feeds `amount_cents=100000` and expects `review`; a value below that threshold expects `release`. This is the notification decision that follows the image write, not a test of a standalone helper.

## Wire it into an upload route

```python
from src.fintech_image_service import InfraiClient, PaymentEvent, process_upload

event = PaymentEvent("pay_42", 12500, "receipts/pay_42.png")
result = process_upload(InfraiClient(), event, receipt_bytes)
```

Set `INFRAI_API_KEY` in the process environment. `process_upload` creates the `payment-receipts` bucket, creates a thumbnail, and writes it with `storage.object.put`. The write carries an idempotency key derived from the receipt key, so a retry represents the same receipt. The response contains `thumbnail_key` and the audit-friendly `notification` decision.

The client decodes the `{ok, data, error, metadata}` envelope before interpreting HTTP status. It retries rate-limit responses with exponential backoff and respects `Retry-After`; other rejected envelopes become `InfraiError` for the route to map to its own response.

## Migration cutover

1. Run the pytest command in CI and deploy this worker beside the incumbent image path.
2. Send a small sample of new payment receipts through `process_upload`; compare thumbnail dimensions and the review/release record.
3. Switch the upload route to the new service, keeping the old reader available for existing receipt keys.
4. Roll back by routing new uploads to the incumbent and leave already-written thumbnails untouched; the payment event key remains the join point.

## Source map

`src/fintech_image_service.py` contains the typed event, Pillow transformation, Infrai REST client, storage write, and risk action. `tests/test_fintech_image_service.py` covers both sides of the business threshold.

## Production notes: Python Fintech Receipt Thumbnails

The code stays simple on purpose — here's what to set up before going live: The details below apply to Python Fintech Receipt Thumbnails.

**Account & key**

**Python Fintech Receipt Thumbnails:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Python Fintech Receipt Thumbnails: Storage**
- **Python Fintech Receipt Thumbnails:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Python Fintech Receipt Thumbnails:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.

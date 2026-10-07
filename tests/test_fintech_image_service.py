from src.fintech_image_service import PaymentEvent, risk_action


def test_large_payment_is_queued_for_review():
    event = PaymentEvent("pay_42", 100_000, "receipts/pay_42.png")
    assert risk_action(event) == "review"


def test_small_payment_is_released():
    event = PaymentEvent("pay_43", 9_999, "receipts/pay_43.png")
    assert risk_action(event) == "release"

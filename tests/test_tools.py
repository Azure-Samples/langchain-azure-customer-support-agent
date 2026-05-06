"""Unit tests for non-LLM tool logic. Mocks the runtime + AppData."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.data_loader import AppData
from app.tools.orders import (
    check_return_eligibility,
    get_order_status,
    initiate_return,
    lookup_order,
)


def _make_runtime(data: AppData):
    return SimpleNamespace(context={"app_data": data})


def _make_data():
    data = AppData()
    today = datetime.now(timezone.utc).isoformat()
    data.orders = [
        {
            "order_id": 1,
            "customer_id": 1,
            "order_date": today,
            "total_amount": 50.0,
            "status": "DELIVERED",
            "items": [{"product_id": 1, "quantity": 1, "unit_price": 50.0, "discount_percent": 0}],
        }
    ]
    data.orders_by_id = {o["order_id"]: o for o in data.orders}
    return data


def test_lookup_order_found():
    data = _make_data()
    runtime = _make_runtime(data)
    result = lookup_order.invoke(
        {"order_id": 1, "tool_call_id": "x"},
        config={"runtime": runtime},  # not actually used because we go direct
    ) if False else None
    # Direct call path: just unwrap the .func
    cmd = lookup_order.func(order_id=1, runtime=runtime, tool_call_id="x")
    assert cmd.update["order_id"] == 1


def test_get_order_status_unknown():
    data = _make_data()
    runtime = _make_runtime(data)
    out = get_order_status.func(order_id=999, runtime=runtime)
    assert "No order" in out


def test_check_return_eligibility_within_window():
    data = _make_data()
    runtime = _make_runtime(data)
    msg = check_return_eligibility.func(order_id=1, line_item_id=0, runtime=runtime)
    assert "Eligible" in msg


def test_initiate_return_creates_record():
    data = _make_data()
    runtime = _make_runtime(data)
    cmd = initiate_return.func(order_id=1, line_item_id=0, reason="defective", runtime=runtime, tool_call_id="x")
    assert len(data.returns) == 1
    assert data.returns[0]["status"] == "requested"
    assert "RMA-" in cmd.update["messages"][0].content

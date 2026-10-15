import asyncio
import json
import threading
import time
import pytest
from fastapi.testclient import TestClient
import httpx

from services.api.src.main import app
from services.api.src.api.live import (
    broadcaster,
    broadcast_line_update,
    LineBroadcaster,
)


@pytest.fixture(autouse=True)
def clean_broadcaster():
    broadcaster.clear()
    yield
    broadcaster.clear()


def test_sse_live_endpoint_returns_event_stream():
    client = TestClient(app)
    with client.stream("GET", "/api/v1/lines/lineA/live?max_events=2") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        assert response.headers.get("cache-control") == "no-cache"


def test_sse_events_live_alias_endpoint():
    client = TestClient(app)
    with client.stream("GET", "/api/v1/lines/lineA/events/live?max_events=2") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]


def test_sse_initial_status_event_payload():
    client = TestClient(app)
    with client.stream("GET", "/api/v1/lines/lineA/live?max_events=1") as response:
        lines = [line for line in response.iter_lines() if line]
        assert "event: status" in lines[0]
        data_line = [line_text for line_text in lines if line_text.startswith("data:")][0]
        payload = json.loads(data_line.replace("data: ", ""))
        assert payload["line_id"] == "lineA"
        assert payload["status"] == "CONNECTED"


def test_broadcaster_isolation_and_lifecycle():
    b = LineBroadcaster()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        q_a1 = b.subscribe("lineA")
        q_a2 = b.subscribe("lineA")
        q_b = b.subscribe("lineB")

        assert b.subscriber_count("lineA") == 2
        assert b.subscriber_count("lineB") == 1
        assert b.subscriber_count() == 3

        # Publish to lineA
        sent = b.publish("lineA", "count", {"total": 10})
        assert sent == 2

        assert q_a1.get_nowait() == ("count", {"total": 10})
        assert q_a2.get_nowait() == ("count", {"total": 10})
        assert q_b.empty()

        # Unsubscribe
        b.unsubscribe("lineA", q_a1)
        assert b.subscriber_count("lineA") == 1

        b.unsubscribe("lineA", q_a2)
        assert b.subscriber_count("lineA") == 0
        b.unsubscribe("lineB", q_b)
        assert b.subscriber_count() == 0
    finally:
        loop.close()


def test_broadcast_line_update_sync_and_async():
    # Test sync call
    count_sync = broadcast_line_update("lineX", "ping", {"ok": True})
    assert int(count_sync) == 0

    # Test async call
    async def async_call():
        return await broadcast_line_update("lineX", "ping", {"ok": True})

    count_async = asyncio.run(async_call())
    assert int(count_async) == 0


@pytest.mark.asyncio
async def test_sse_receives_broadcast_events_via_async_client():
    received_events = []

    async def push_updates():
        # Short pause to ensure subscriber is registered
        await asyncio.sleep(0.05)
        await broadcast_line_update("line1", "count", {"total_today": 48250, "rate_per_min": 120.0})
        await asyncio.sleep(0.02)
        await broadcast_line_update("line1", "health", {"fps": 30.0, "latency_ms": 38.2, "status": "ONLINE"})
        await asyncio.sleep(0.02)
        await broadcast_line_update("line1", "alarm", {"type": "LOW_RATE", "severity": "WARNING", "msg": "Rate dropped"})

    push_task = asyncio.create_task(push_updates())

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # Request stream with max_events=4 (1 status + 3 broadcasts)
        async with client.stream("GET", "/api/v1/lines/line1/live?max_events=4") as response:
            assert response.status_code == 200
            current_event = None
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("event: "):
                    current_event = line.replace("event: ", "").strip()
                elif line.startswith("data: ") and current_event:
                    data = json.loads(line.replace("data: ", ""))
                    received_events.append((current_event, data))
                    current_event = None

    await push_task

    assert len(received_events) == 4
    assert received_events[0][0] == "status"
    assert received_events[0][1]["line_id"] == "line1"

    assert received_events[1][0] == "count"
    assert received_events[1][1]["total_today"] == 48250

    assert received_events[2][0] == "health"
    assert received_events[2][1]["fps"] == 30.0

    assert received_events[3][0] == "alarm"
    assert received_events[3][1]["severity"] == "WARNING"


@pytest.mark.asyncio
async def test_sse_heartbeat_generation():
    heartbeats = []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # Request stream with short heartbeat interval (0.05s) and max_events=2
        async with client.stream(
            "GET", "/api/v1/lines/lineHb/live?heartbeat_interval=0.05&max_events=2"
        ) as response:
            assert response.status_code == 200
            current_event = None
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("event: "):
                    current_event = line.replace("event: ", "").strip()
                elif line.startswith("data: ") and current_event:
                    data = json.loads(line.replace("data: ", ""))
                    if current_event == "heartbeat":
                        heartbeats.append(data)
                    current_event = None

    assert len(heartbeats) == 1
    assert heartbeats[0]["line_id"] == "lineHb"
    assert heartbeats[0]["status"] == "ONLINE"


@pytest.mark.asyncio
async def test_sse_unsubscribes_on_completion():
    assert broadcaster.subscriber_count("lineUnsub") == 0

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        async with client.stream("GET", "/api/v1/lines/lineUnsub/live?max_events=1") as response:
            assert response.status_code == 200
            async for _ in response.aiter_lines():
                pass

    # Verify unsubscription happened
    assert broadcaster.subscriber_count("lineUnsub") == 0


@pytest.mark.asyncio
async def test_sse_timeout_parameter():
    start = time.monotonic()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        async with client.stream(
            "GET", "/api/v1/lines/lineTimeout/live?timeout=0.1&heartbeat_interval=10.0"
        ) as response:
            assert response.status_code == 200
            async for _ in response.aiter_lines():
                pass
    elapsed = time.monotonic() - start
    assert elapsed < 1.0


def test_format_sse_helper():
    from services.api.src.api.live import format_sse

    # With dict
    res1 = format_sse("count", {"total": 5})
    assert res1 == 'event: count\ndata: {"total": 5}\n\n'

    # With event id
    res2 = format_sse("ping", "pong", event_id=42)
    assert res2 == "event: ping\ndata: pong\nid: 42\n\n"


def test_queue_overflow_drops_oldest():
    b = LineBroadcaster()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Subscribe queue with small maxsize
        q = b.subscribe("lineSmall", maxsize=2)
        b.publish("lineSmall", "ev1", {"num": 1})
        b.publish("lineSmall", "ev2", {"num": 2})
        # Third publish overflows maxsize 2, drops oldest (ev1)
        b.publish("lineSmall", "ev3", {"num": 3})

        assert q.qsize() == 2
        item1 = q.get_nowait()
        assert item1 == ("ev2", {"num": 2})
        item2 = q.get_nowait()
        assert item2 == ("ev3", {"num": 3})
    finally:
        loop.close()


def test_threadsafe_broadcast_with_testclient():
    client = TestClient(app)

    def background_sender():
        time.sleep(0.04)
        broadcast_line_update("lineSync", "alarm", {"msg": "warning: slow line"})

    sender_thread = threading.Thread(target=background_sender)
    sender_thread.start()

    with client.stream("GET", "/api/v1/lines/lineSync/live?max_events=2") as response:
        assert response.status_code == 200
        lines = [line for line in response.iter_lines() if line]
        assert any("event: status" in line_item for line_item in lines)
        assert any("event: alarm" in line_item for line_item in lines)

    sender_thread.join()


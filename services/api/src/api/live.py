import asyncio
import json
import threading
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from services.api.src.api.auth import UserDTO, require_role
from services.api.src.services.preview import (
    FrameGenerator,
    record_viewer_activity,
    store_live_frame,
)

router = APIRouter(prefix="/api/v1/lines", tags=["live"])


class AwaitableInt(int):
    """Integer that can also be awaited in async contexts."""

    def __await__(self):
        async def _coro():
            return int(self)

        return _coro().__await__()


class LineBroadcaster:
    """In-memory pub/sub broadcaster managing asyncio queues per line subscriber."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[tuple[asyncio.Queue, asyncio.AbstractEventLoop]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, line_id: str, maxsize: int = 100) -> asyncio.Queue:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        with self._lock:
            if line_id not in self._subscribers:
                self._subscribers[line_id] = set()
            self._subscribers[line_id].add((queue, loop))
        return queue

    def unsubscribe(self, line_id: str, queue: asyncio.Queue) -> None:
        with self._lock:
            if line_id in self._subscribers:
                self._subscribers[line_id] = {
                    (q, loop) for (q, loop) in self._subscribers[line_id] if q is not queue
                }
                if not self._subscribers[line_id]:
                    del self._subscribers[line_id]

    def subscriber_count(self, line_id: str | None = None) -> int:
        with self._lock:
            if line_id is not None:
                return len(self._subscribers.get(line_id, set()))
            return sum(len(subs) for subs in self._subscribers.values())

    def clear(self) -> None:
        with self._lock:
            self._subscribers.clear()

    def publish(self, line_id: str, event_type: str, data: Any) -> AwaitableInt:
        with self._lock:
            subs = list(self._subscribers.get(line_id, set()))

        sent = 0
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        for queue, loop in subs:
            if loop.is_closed():
                continue

            def _enqueue(q=queue, item=(event_type, data)):
                try:
                    q.put_nowait(item)
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        q.put_nowait(item)
                    except asyncio.QueueFull:
                        pass

            if loop.is_running() and loop is not current_loop:
                loop.call_soon_threadsafe(_enqueue)
            else:
                _enqueue()
            sent += 1

        return AwaitableInt(sent)


broadcaster = LineBroadcaster()


def broadcast_line_update(line_id: str, event_type: str, data: Any) -> AwaitableInt:
    """Broadcast an update to all active SSE subscribers of a line."""
    return broadcaster.publish(line_id, event_type, data)


def format_sse(event: str, data: Any, event_id: str | int | None = None) -> str:
    """Format a Server-Sent Event message."""
    if hasattr(data, "model_dump"):
        payload = json.dumps(data.model_dump(mode="json"), default=str)
    elif isinstance(data, (dict, list)):
        payload = json.dumps(data, default=str)
    else:
        payload = str(data)
    msg = f"event: {event}\ndata: {payload}\n"
    if event_id is not None:
        msg += f"id: {event_id}\n"
    msg += "\n"
    return msg


@router.get("/{line_id}/live")
@router.get("/{line_id}/events/live")
async def live_stream(
    line_id: str,
    request: Request,
    max_events: int | None = Query(default=None, description="Max events to yield before closing"),
    timeout: float | None = Query(default=None, description="Max duration in seconds before closing"),
    heartbeat_interval: float = Query(default=15.0, description="Heartbeat interval in seconds"),
):
    """Server-Sent Events endpoint delivering real-time line telemetry."""
    async def event_generator():
        queue = broadcaster.subscribe(line_id)
        event_count = 0
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # 1. Initial connection status event
            init_data = {"line_id": line_id, "status": "CONNECTED", "total_today": 0}
            yield format_sse("status", init_data)
            event_count += 1

            while True:
                if max_events is not None and event_count >= max_events:
                    break

                now = loop.time()
                if timeout is not None and (now - start_time) >= timeout:
                    break

                if await request.is_disconnected():
                    break

                wait_timeout = heartbeat_interval
                if timeout is not None:
                    remaining = timeout - (now - start_time)
                    if remaining <= 0:
                        break
                    wait_timeout = min(wait_timeout, remaining)

                try:
                    event_type, data = await asyncio.wait_for(queue.get(), timeout=wait_timeout)
                    yield format_sse(event_type, data)
                    event_count += 1
                except asyncio.TimeoutError:
                    if timeout is not None and (loop.time() - start_time) >= timeout:
                        break
                    heartbeat_data = {"line_id": line_id, "fps": 30.0, "status": "ONLINE"}
                    yield format_sse("heartbeat", heartbeat_data)
                    event_count += 1

        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(line_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{line_id}/preview")
async def preview_stream(
    line_id: str,
    request: Request,
    max_frames: int | None = Query(default=None, ge=0, description="Max frames to yield before closing"),
):
    """MJPEG live preview stream delivering synthetic annotated camera feed."""
    if not line_id or not line_id.strip():
        raise HTTPException(status_code=400, detail="Invalid line_id")

    limit_frames = max_frames if isinstance(max_frames, int) else None

    async def frame_stream():
        frame_idx = 0
        try:
            while True:
                if limit_frames is not None and frame_idx >= limit_frames:
                    break
                if await request.is_disconnected():
                    break
                record_viewer_activity(line_id)
                jpeg_bytes = await asyncio.to_thread(FrameGenerator.generate_jpeg_frame, line_id, frame_idx)
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                )
                frame_idx += 1
                await asyncio.sleep(0.066)  # ~15 fps
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        frame_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.post("/{line_id}/frame", status_code=status.HTTP_204_NO_CONTENT)
async def upload_frame(
    line_id: str,
    request: Request,
    current_user: UserDTO = Depends(require_role(["operator", "admin"])),
) -> Response:
    """Ingest uploaded JPEG frame from edge device or authorized operator/admin."""
    line_slug = line_id.strip()
    if not line_slug:
        raise HTTPException(status_code=400, detail="Invalid line_id")

    user_role = (current_user.role or "").lower()
    if user_role != "admin":
        if current_user.username.startswith("device:"):
            allowed_line = current_user.username[len("device:"):]
            if allowed_line != line_slug:
                raise HTTPException(
                    status_code=403,
                    detail=f"Token not authorized for this line (authorized: '{allowed_line}')",
                )

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty frame body")

    if len(body) > 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Frame exceeds maximum size limit of 1048576 bytes",
        )

    if len(body) < 4 or not body.startswith(b"\xff\xd8"):
        raise HTTPException(
            status_code=400,
            detail="Invalid image format: must be JPEG (SOI marker missing)",
        )

    store_live_frame(line_slug, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



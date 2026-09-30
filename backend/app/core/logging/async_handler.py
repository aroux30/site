"""Non-blocking asynchronous logging handler with in-memory buffering.

Offloads all formatting, serialization, and I/O (stdout, disk, network)
from the ASGI event loop and application threads to a dedicated background
worker thread via a bounded memory queue.
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import logging.handlers
import queue
import sys
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


class NonFormattingQueueHandler(logging.handlers.QueueHandler):
    """QueueHandler that enqueues raw LogRecord without premature formatting.

    Standard library QueueHandler formats the record inside ``prepare()`` on the
    calling thread, which wastes CPU cycles on the ASGI event loop. This class
    preserves the raw LogRecord so formatting and serialization occur exclusively
    in the background QueueListener thread.
    """

    def __init__(self, log_queue: queue.Queue[Any], drop_on_overflow: bool = True) -> None:
        super().__init__(log_queue)
        self.drop_on_overflow = drop_on_overflow
        self._dropped_count: int = 0
        self._lock = threading.Lock()

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        """Return the unformatted record to defer formatting to the listener."""
        return record

    def enqueue(self, record: logging.LogRecord) -> None:
        """Enqueue record non-blockingly to protect event loop latency."""
        try:
            if self.drop_on_overflow:
                self.queue.put_nowait(record)
            else:
                self.queue.put_nowait(record)  # non-blocking (queue.Queue at runtime)
        except queue.Full:
            with self._lock:
                self._dropped_count += 1
            # Drop on queue overflow; add ring-buffer spillover when sustained log rate > 50k eps.
            pass

    @property
    def dropped_count(self) -> int:
        """Number of log records dropped due to buffer overflow."""
        with self._lock:
            return self._dropped_count


class AsyncLogQueueManager:
    """Manages the lifecycle of the async logging queue and background worker listener."""

    def __init__(
        self,
        handlers: Sequence[logging.Handler] | None = None,
        max_queue_size: int = 10000,
        drop_on_overflow: bool = True,
    ) -> None:
        self.max_queue_size = max_queue_size
        self.drop_on_overflow = drop_on_overflow
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_queue_size)
        self._handlers: list[logging.Handler] = list(
            handlers or [logging.StreamHandler(sys.stdout)]
        )
        self._queue_handler: NonFormattingQueueHandler = NonFormattingQueueHandler(
            self._queue, drop_on_overflow=drop_on_overflow
        )
        self._listener: logging.handlers.QueueListener | None = None
        self._started: bool = False
        self._lock = threading.Lock()

    def start(self) -> NonFormattingQueueHandler:
        """Start the background QueueListener worker thread."""
        with self._lock:
            if not self._started:
                self._listener = logging.handlers.QueueListener(
                    self._queue,
                    *self._handlers,
                    respect_handler_level=True,
                )
                self._listener.start()
                self._started = True
                atexit.register(self.stop)
            return self._queue_handler

    def stop(self, timeout: float = 3.0) -> None:
        """Gracefully drain the queue and stop the background worker thread."""
        with self._lock:
            if self._started and self._listener is not None:
                with contextlib.suppress(Exception):
                    self._listener.stop()
                self._started = False

    def flush(self, timeout: float = 3.0) -> None:
        """Block until every enqueued record has actually been written.

        Polling ``queue.empty()`` is not sufficient: the listener thread takes
        a record off the queue and then formats and writes it, so the queue can
        read as empty while a record is still in flight — and a caller that
        reads the log file at that moment observes a torn or missing line.

        Instead, stop the listener. ``QueueListener.stop()`` enqueues a
        sentinel and joins the thread, which drains the queue in FIFO order
        and guarantees every record enqueued before this call has been
        handled. The listener is then restarted so the manager keeps working.
        """
        with self._lock:
            if not self._started or self._listener is None:
                return

            listeners_to_stop = self._listener
            handlers = self._handlers

        # stop() outside the lock: it joins the worker thread and must not
        # deadlock against a concurrent start(). It is idempotent per instance.
        with contextlib.suppress(Exception):
            listeners_to_stop.stop()

        for h in handlers:
            with contextlib.suppress(Exception):
                h.flush()

        # Restart the listener so logging continues after the flush.
        with self._lock:
            if self._started and self._listener is listeners_to_stop:
                self._listener = logging.handlers.QueueListener(
                    self._queue,
                    *self._handlers,
                    respect_handler_level=True,
                )
                self._listener.start()

    @property
    def is_running(self) -> bool:
        """Check if listener is currently active."""
        return self._started

    @property
    def handler(self) -> NonFormattingQueueHandler:
        """Get the non-formatting QueueHandler instance."""
        return self._queue_handler

    @property
    def queue(self) -> queue.Queue[Any]:
        """Get the underlying bounded in-memory queue."""
        return self._queue

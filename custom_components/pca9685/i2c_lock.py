import asyncio
import logging
import time

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class LockWaitStats:
    """Collect and periodically report lock-wait statistics."""

    def __init__(self, lock_store_key: str, bus: int) -> None:
        self._lock_store_key = lock_store_key
        self._bus = bus
        self._summary_interval_s = 60.0
        self._slow_wait_threshold_s = 0.05
        self._window_start = time.monotonic()
        self._samples = 0
        self._total_wait_s = 0.0
        self._max_wait_s = 0.0
        self._slow_waits = 0

    def record_wait(self, wait_s: float) -> None:
        self._samples += 1
        self._total_wait_s += wait_s
        self._max_wait_s = max(self._max_wait_s, wait_s)
        if wait_s >= self._slow_wait_threshold_s:
            self._slow_waits += 1

        now = time.monotonic()
        if now - self._window_start < self._summary_interval_s:
            return

        if self._samples > 0:
            _LOGGER.debug(
                (
                    "I2C lock stats key=%s bus=%s samples=%d avg_wait_ms=%.2f "
                    "max_wait_ms=%.2f slow_waits=%d slow_threshold_ms=%.1f"
                ),
                self._lock_store_key,
                self._bus,
                self._samples,
                (self._total_wait_s / self._samples) * 1000.0,
                self._max_wait_s * 1000.0,
                self._slow_waits,
                self._slow_wait_threshold_s * 1000.0,
            )

        self._window_start = now
        self._samples = 0
        self._total_wait_s = 0.0
        self._max_wait_s = 0.0
        self._slow_waits = 0


class ThreadLockAsyncAdapter:
    """Adapter that lets async code share a threading-style lock."""

    def __init__(self, lock) -> None:
        self._lock = lock

    async def acquire(self) -> bool:
        return await asyncio.to_thread(self._lock.acquire)

    def release(self) -> None:
        self._lock.release()

    def locked(self) -> bool:
        return bool(getattr(self._lock, "locked", lambda: False)())

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.release()


class InstrumentedAsyncLock:
    """Async lock wrapper with rate-limited wait telemetry."""

    _copilot_instrumented_i2c_lock = True

    def __init__(self, lock, stats: LockWaitStats) -> None:
        self._lock = lock
        self._stats = stats

    async def acquire(self) -> bool:
        start = time.monotonic()
        result = await self._lock.acquire()
        self._stats.record_wait(time.monotonic() - start)
        return result

    def release(self) -> None:
        self._lock.release()

    def locked(self) -> bool:
        return bool(getattr(self._lock, "locked", lambda: False)())

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.release()


def _normalize_async_lock(lock):
    if getattr(lock, "_copilot_instrumented_i2c_lock", False):
        return lock

    if isinstance(lock, asyncio.Lock):
        return lock

    if hasattr(lock, "__aenter__") and hasattr(lock, "__aexit__") and hasattr(lock, "acquire") and hasattr(lock, "release"):
        return lock

    if hasattr(lock, "acquire") and hasattr(lock, "release"):
        return ThreadLockAsyncAdapter(lock)

    raise TypeError(
        f"Expected async-capable lock, got {type(lock).__name__} "
        f"without async context manager or acquire/release support"
    )


def get_i2c_bus_lock(
    hass: HomeAssistant,
    lock_store_key: str,
    bus: int,
) -> tuple[object, bool]:
    """Return the shared async lock for one I2C bus."""
    if lock_store_key not in hass.data:
        hass.data[lock_store_key] = {}

    created = False
    bus_locks = hass.data[lock_store_key]
    if bus not in bus_locks:
        bus_locks[bus] = asyncio.Lock()
        created = True

    lock = _normalize_async_lock(bus_locks[bus])
    if lock is not bus_locks[bus]:
        bus_locks[bus] = lock

    if getattr(lock, "_copilot_instrumented_i2c_lock", False):
        return lock, created

    instrumented = InstrumentedAsyncLock(lock, LockWaitStats(lock_store_key, bus))
    bus_locks[bus] = instrumented
    return instrumented, created

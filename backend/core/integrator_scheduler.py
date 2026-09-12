"""Integrator scheduler worker lifecycle management."""

import asyncio
import contextlib
import logging

logger = logging.getLogger(__name__)


async def run_scheduler_loop(
    tick_fn,
    interval_seconds: int,
) -> None:
    logger.info(
        "Integrator scheduler worker started: interval_seconds=%s",
        interval_seconds,
    )
    try:
        while True:
            try:
                result = await tick_fn()
                if result.get("due_count") or result.get("status") == "skipped":
                    logger.info(
                        "Integrator scheduler tick: status=%s checked=%s due=%s executed=%s",
                        result.get("status", "ok"),
                        result.get("checked", 0),
                        result.get("due_count", 0),
                        result.get("executed", False),
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Integrator scheduler tick failed")
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Integrator scheduler worker stopped")
        raise


class SchedulerWorker:
    """Manages the lifecycle of an integrator scheduler background task."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    def start(self, tick_fn, config: dict, runtime_logger=None) -> bool:
        log = runtime_logger or logger
        if not config["enabled"]:
            log.info(
                "Integrator scheduler worker disabled: enabled_source=%s interval_seconds=%s",
                config["enabled_source"],
                config["interval_seconds"],
            )
            return False

        if self._task is not None and not self._task.done():
            log.info("Integrator scheduler worker already running")
            return True

        self._task = asyncio.create_task(
            run_scheduler_loop(tick_fn, int(config["interval_seconds"])),
            name="integrator-scheduler-worker",
        )
        return True

    async def stop(self) -> bool:
        task = self._task
        if task is None:
            return False
        self._task = None
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return True

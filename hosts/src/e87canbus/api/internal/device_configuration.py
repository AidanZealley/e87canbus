"""Durable button-pad scenes and bounded configuration subscriptions."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass, field

from e87canbus.adapters.sqlite_device_state import (
    SqliteDeviceStateRepository,
    StoredButtonPadConfiguration,
)
from e87canbus.api.auth import DeviceRole
from e87canbus.api.models.button_pad import ButtonPadScene
from e87canbus.kernel import StateTopic
from e87canbus.service import ControllerLoop, ControllerLoopSnapshot, RuntimeExecution

KEEPALIVE_INTERVAL_S = 15.0


@dataclass(eq=False, slots=True)
class ConfigurationSubscriber:
    initial: StoredButtonPadConfiguration
    request_task: asyncio.Task[object]
    pending: StoredButtonPadConfiguration | None = None
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    closed: bool = False


class ButtonPadConfigurationService:
    def __init__(self, controller: ControllerLoop, repository: SqliteDeviceStateRepository) -> None:
        self._controller = controller
        self._repository = repository
        self._thread_lock = threading.Lock()
        self._latest: ControllerLoopSnapshot | None = None
        self._wake = asyncio.Event()
        self._operation_lock = asyncio.Lock()
        self._subscribers: dict[str, set[ConfigurationSubscriber]] = {}
        self._task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopping = False
        self._minimum_revision = -1

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(self._run(), name="device-configuration")
        self._offer_snapshot(self._controller.snapshot())

    async def stop(self, timeout_s: float) -> None:
        self._stopping = True
        task = self._task
        if task is not None:
            task.cancel()
            with suppress(TimeoutError):
                await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout_s)
        async with self._operation_lock:
            self._close_subscribers()
        self._loop = None
        self._task = None

    def offer(self, execution: RuntimeExecution) -> None:
        if StateTopic.BUTTONS in execution.changed_topics and not self._stopping:
            self._offer_snapshot(self._controller.snapshot())

    def _offer_snapshot(self, snapshot: ControllerLoopSnapshot) -> None:
        with self._thread_lock:
            if self._latest is None or snapshot.revision >= self._latest.revision:
                self._latest = snapshot
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._wake.set)

    async def subscribe(
        self, device_id: str, request_task: asyncio.Task[object]
    ) -> ConfigurationSubscriber:
        async with self._operation_lock:
            if self._stopping or self._task is None or self._task.done():
                raise RuntimeError("device configuration service is not running")
            snapshot = self._controller.snapshot()
            scene = ButtonPadScene.from_resolved_buttons(snapshot.application.button_pad)
            initial = await asyncio.to_thread(
                self._repository.get_or_create_configuration,
                device_id,
                DeviceRole.BUTTON_PAD,
                scene,
            )
            initial = await asyncio.to_thread(
                self._repository.replace_configuration_if_changed,
                device_id,
                DeviceRole.BUTTON_PAD,
                scene,
            )
            subscriber = ConfigurationSubscriber(initial, request_task)
            self._subscribers.setdefault(device_id, set()).add(subscriber)
            self._minimum_revision = max(self._minimum_revision, snapshot.revision)
            return subscriber

    def unsubscribe(self, subscriber: ConfigurationSubscriber) -> None:
        subscribers = self._subscribers.get(subscriber.initial.device_id)
        if subscribers is not None:
            subscribers.discard(subscriber)
            if not subscribers:
                del self._subscribers[subscriber.initial.device_id]
        subscriber.closed = True

    async def events(self, subscriber: ConfigurationSubscriber) -> AsyncIterator[str]:
        try:
            yield _record(subscriber.initial)
            while not subscriber.closed:
                pending = subscriber.pending
                subscriber.pending = None
                if pending is not None:
                    yield _record(pending)
                    continue
                subscriber.wake.clear()
                try:
                    async with asyncio.timeout(KEEPALIVE_INTERVAL_S):
                        await subscriber.wake.wait()
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self.unsubscribe(subscriber)

    async def _run(self) -> None:
        try:
            while True:
                await self._wake.wait()
                self._wake.clear()
                with self._thread_lock:
                    snapshot = self._latest
                if snapshot is None or snapshot.revision < self._minimum_revision:
                    continue
                await self._publish(snapshot)
        finally:
            self._close_subscribers()

    async def _publish(self, snapshot: ControllerLoopSnapshot) -> None:
        async with self._operation_lock:
            if snapshot.revision < self._minimum_revision:
                return
            scene = ButtonPadScene.from_resolved_buttons(snapshot.application.button_pad)
            stored = await asyncio.to_thread(self._repository.list_button_pad_configurations)
            for current in stored:
                replacement = await asyncio.to_thread(
                    self._repository.replace_configuration_if_changed,
                    current.device_id,
                    DeviceRole.BUTTON_PAD,
                    scene,
                )
                if replacement.generation != current.generation:
                    for subscriber in tuple(self._subscribers.get(current.device_id, ())):
                        if subscriber.pending is not None:
                            self._close(subscriber)
                            self.unsubscribe(subscriber)
                        else:
                            subscriber.pending = replacement
                            subscriber.wake.set()
            self._minimum_revision = max(self._minimum_revision, snapshot.revision)

    @staticmethod
    def _close(subscriber: ConfigurationSubscriber) -> None:
        subscriber.closed = True
        subscriber.wake.set()
        if not subscriber.request_task.done():
            subscriber.request_task.cancel()

    def _close_subscribers(self) -> None:
        for subscribers in self._subscribers.values():
            for subscriber in subscribers:
                self._close(subscriber)
        self._subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        return sum(map(len, self._subscribers.values()))


def _record(envelope: StoredButtonPadConfiguration) -> str:
    return (
        'data: {"generation":'
        f'{envelope.generation},"configuration":{envelope.configuration.model_dump_json()}}}\n\n'
    )

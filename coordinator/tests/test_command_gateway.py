import asyncio
from concurrent.futures import Future
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest
from e87canbus.api.errors import ApiProblem
from e87canbus.api.internal.commands import submit_runtime_work
from e87canbus.config import default_config
from e87canbus.service import ControllerInboxFull, ControllerServiceNotRunning


class FakeService:
    def __init__(self, outcome: Future[object] | Exception) -> None:
        self.config = replace(default_config(), runtime_command_timeout_s=0.01)
        self.outcome = outcome
        self.submissions: list[object] = []

    def submit(self, work: object) -> Future[object]:
        self.submissions.append(work)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def app_with(service: FakeService) -> Any:
    return SimpleNamespace(state=SimpleNamespace(controller_service=service))


def completed(value: object = object()) -> Future[object]:
    future: Future[object] = Future()
    future.set_result(value)
    return future


def failed(error: Exception) -> Future[object]:
    future: Future[object] = Future()
    future.set_exception(error)
    return future


def test_gateway_submits_exactly_once_and_returns_the_runtime_result() -> None:
    result = object()
    service = FakeService(completed(result))
    command = object()

    returned = asyncio.run(submit_runtime_work(app_with(service), command))

    assert returned is result
    assert service.submissions == [command]


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        (ControllerInboxFull("full"), "runtime_queue_full"),
        (ControllerServiceNotRunning("stopped"), "controller_unavailable"),
    ],
)
def test_gateway_maps_rejected_submission_to_stable_503(
    failure: Exception,
    code: str,
) -> None:
    service = FakeService(failure)

    with pytest.raises(ApiProblem) as caught:
        asyncio.run(submit_runtime_work(app_with(service), object()))

    assert caught.value.status_code == 503
    assert caught.value.code == code
    assert len(service.submissions) == 1


def test_gateway_timeout_is_finite_and_does_not_cancel_ambiguous_work() -> None:
    future: Future[object] = Future()
    service = FakeService(future)

    with pytest.raises(ApiProblem) as caught:
        asyncio.run(submit_runtime_work(app_with(service), object()))

    assert caught.value.status_code == 503
    assert caught.value.code == "command_timeout"
    assert future.cancelled() is False


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [
        (ValueError("invalid"), 422, "validation_error"),
        (RuntimeError("failed"), 503, "controller_runtime_error"),
    ],
)
def test_gateway_maps_processing_failures(
    failure: Exception,
    status: int,
    code: str,
) -> None:
    service = FakeService(failed(failure))

    with pytest.raises(ApiProblem) as caught:
        asyncio.run(submit_runtime_work(app_with(service), object()))

    assert caught.value.status_code == status
    assert caught.value.code == code

"""Durable scene publication and independent button-pad generations."""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from e87canbus.api.auth import DeviceRole
from e87canbus.api.main import create_app
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    ButtonSlot,
    button_profile_definition_with,
)
from e87canbus.domain.intents import ToggleAutomaticAssistance
from e87canbus.kernel import ActivateButtonProfile


async def wait_for_generation(repository, device_id: str, generation: int) -> None:
    async def poll() -> None:
        while (
            repository.get_configuration(device_id, DeviceRole.BUTTON_PAD).generation
            < generation
        ):
            await asyncio.sleep(0.005)

    await asyncio.wait_for(poll(), 2)


@pytest.mark.asyncio
async def test_first_contact_replacement_and_restart(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    first_id, second_id, late_id = (str(uuid4()) for _ in range(3))
    app = create_app(profile_database_path=path, simulate_button_pad=False)
    async with app.router.lifespan_context(app):
        configuration = app.state.device_configuration
        task = asyncio.create_task(asyncio.Event().wait())
        first = await configuration.subscribe(first_id, task)
        second = await configuration.subscribe(second_id, task)
        first_events = configuration.events(first)
        second_events = configuration.events(second)
        initial = json.loads((await anext(first_events)).removeprefix("data: "))
        assert initial["generation"] == 0
        assert len(initial["configuration"]["buttons"]) == 16
        assert (await anext(second_events)) == (
            "data: " + json.dumps(initial, separators=(",", ":")) + "\n\n"
        )
        profile = ActiveButtonProfile(
            "test",
            button_profile_definition_with(
                {5: ButtonSlot(ToggleAutomaticAssistance(), (12, 34, 56))}
            ),
        )
        saved = app.state.button_profile_repository.create_profile("test", profile.definition)
        app.state.button_profile_repository.select_profile(saved.profile_id, saved.revision)
        app.state.controller_loop.submit(ActivateButtonProfile(profile)).result(timeout=2)
        await wait_for_generation(app.state.device_state_repository, first_id, 1)
        await wait_for_generation(app.state.device_state_repository, second_id, 1)
        assert app.state.device_state_repository.get_configuration(
            second_id, DeviceRole.BUTTON_PAD
        ).generation == 1
        updated = json.loads((await anext(first_events)).removeprefix("data: "))
        assert updated["generation"] == 1
        assert updated["configuration"]["buttons"][5] == {
            "assigned": True,
            "colour": [12, 34, 56],
            "animation": None,
        }
        late = await configuration.subscribe(late_id, task)
        late_events = configuration.events(late)
        late_initial = json.loads((await anext(late_events)).removeprefix("data: "))
        assert late_initial["generation"] == 0
        assert late_initial["configuration"] == updated["configuration"]
        await late_events.aclose()
        await first_events.aclose()
        await second_events.aclose()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert configuration.subscriber_count == 0

    restarted = create_app(profile_database_path=path, simulate_button_pad=False)
    async with restarted.router.lifespan_context(restarted):
        task = asyncio.create_task(asyncio.Event().wait())
        subscriber = await restarted.state.device_configuration.subscribe(first_id, task)
        events = restarted.state.device_configuration.events(subscriber)
        # The coordinator's selected profile is restored before the service starts.
        assert json.loads((await anext(events)).removeprefix("data: "))["generation"] == 1
        await events.aclose()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

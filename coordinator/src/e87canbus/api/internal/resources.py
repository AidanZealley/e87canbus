"""Precise durable-resource change publication."""

from typing import Literal

from fastapi import FastAPI

from e87canbus.api.models.resources import ResourceChangedEvent


async def publish_resource_change(
    app: FastAPI,
    *,
    resource: Literal["settings", "steering_profile"],
    resource_id: str | None,
    revision: int,
) -> None:
    event = ResourceChangedEvent(
        resource=resource,
        id=resource_id,
        revision=revision,
    )
    app.state.live_publisher.offer_resource(event)

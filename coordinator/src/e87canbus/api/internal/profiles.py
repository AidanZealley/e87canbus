"""One mapping from revisioned-profile repository failures onto HTTP problems.

Steering and button profiles raise the same exception vocabulary, so they answer with
the same status codes and error codes; keeping that table in one place is what stops
the two surfaces from drifting apart.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

from e87canbus.api.errors import ApiProblem
from e87canbus.domain.revisioned_profiles import (
    ProfileNameConflictError,
    ProfileNotFoundError,
    ProfileProtectedError,
    ProfileRevisionConflictError,
    ProfileStorageError,
)

T = TypeVar("T")


async def repository_operation(operation: Callable[[], T]) -> T:
    """Run one blocking repository call off the event loop, translating its failures."""

    try:
        return await asyncio.to_thread(operation)
    except ProfileRevisionConflictError as exc:
        raise ApiProblem(
            409,
            "profile_revision_conflict",
            str(exc),
            current_revision=exc.actual_revision,
        ) from exc
    except ProfileNameConflictError as exc:
        raise ApiProblem(409, "profile_name_conflict", str(exc)) from exc
    except ProfileProtectedError as exc:
        raise ApiProblem(409, "profile_protected", str(exc)) from exc
    except ProfileNotFoundError as exc:
        raise ApiProblem(404, "profile_not_found", str(exc)) from exc
    except ProfileStorageError as exc:
        raise ApiProblem(503, "profile_storage_error", str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc

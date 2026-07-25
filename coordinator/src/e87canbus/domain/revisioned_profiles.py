"""Shared vocabulary for revisioned, user-authored profiles.

Steering curves and button-pad mappings are stored the same way: a named row carrying
a monotonic ``revision`` used for optimistic concurrency. They therefore fail the same
ways, so they share one exception hierarchy and one revision rule. The human-readable
``kind`` ("steering profile", "button profile") is data on the error rather than a
parallel class tree, which keeps the API error mapping single-sourced.
"""

from __future__ import annotations


class ProfileRepositoryError(Exception):
    """Base class for failures exposed by a revisioned profile repository."""


class ProfileStorageError(ProfileRepositoryError):
    """The repository could not safely read or commit its durable state."""


class StoredProfileDataError(ProfileStorageError):
    """A stored row failed its own integrity checks and must not be trusted."""

    def __init__(self, kind: str, profile_id: str, reason: str) -> None:
        self.profile_id, self.reason = profile_id, reason
        super().__init__(f"invalid stored {kind} {profile_id}: {reason}")


class ProfileNotFoundError(ProfileRepositoryError):
    def __init__(self, kind: str, profile_id: str) -> None:
        self.profile_id = profile_id
        super().__init__(f"{kind} not found: {profile_id}")


class ProfileNameConflictError(ProfileRepositoryError):
    def __init__(self, kind: str, name: str) -> None:
        self.name = name
        super().__init__(f"{kind} name already exists: {name}")


class ProfileProtectedError(ProfileRepositoryError):
    """A profile the running system depends on may not be mutated or removed."""


class ProfileRevisionConflictError(ProfileRepositoryError):
    def __init__(
        self, kind: str, profile_id: str, expected_revision: int, actual_revision: int
    ) -> None:
        self.profile_id = profile_id
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        super().__init__(
            f"{kind} {profile_id} is at revision {actual_revision}, not {expected_revision}"
        )


def validate_saved_profile_revision(
    revision: int | None,
    field_name: str = "saved_profile_revision",
) -> None:
    """Validate a pointer to a stored profile revision; ``None`` means 'not from storage'.

    Every layer that carries such a pointer (kernel inputs, kernel configuration and
    the storage adapter) shares this one rule so a revision can never mean something
    different depending on where it entered the system.
    """

    if revision is not None and (type(revision) is not int or revision < 1):
        raise ValueError(f"{field_name} must be a positive integer")


def validate_expected_revision(
    revision: int | None,
    field_name: str = "expected_revision",
) -> None:
    """Validate an optimistic-concurrency precondition, which may never be absent.

    Storage callers must name the revision they believe they are replacing; ``None``
    is only meaningful in the runtime, where it marks state that never came from disk.
    """

    if revision is None:
        raise ValueError(f"{field_name} must be a positive integer")
    validate_saved_profile_revision(revision, field_name)

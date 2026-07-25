"""The one revisioned-profile mechanism shared by steering and button profiles."""

from pathlib import Path
from typing import Any

import pytest
from e87canbus.adapters.sqlite_button_profiles import SqliteButtonProfileRepository
from e87canbus.adapters.sqlite_profiles import SqliteSteeringProfileRepository
from e87canbus.adapters.sqlite_revisioned_profiles import (
    RevisionedProfileSpec,
    SqliteRevisionedProfileRepository,
)
from e87canbus.domain.button_profiles import empty_button_profile_definition
from e87canbus.domain.revisioned_profiles import (
    ProfileNameConflictError,
    ProfileNotFoundError,
    ProfileRevisionConflictError,
    validate_expected_revision,
    validate_saved_profile_revision,
)
from e87canbus.domain.steering import BUILT_IN_STEERING_CURVE

MISSING_ID = "00000000-0000-4000-8000-000000000000"


def _button(path: Path) -> tuple[SqliteButtonProfileRepository, Any]:
    repository = SqliteButtonProfileRepository(path)
    repository.initialize()
    return repository, empty_button_profile_definition()


def _steering(path: Path) -> tuple[SqliteSteeringProfileRepository, Any]:
    repository = SqliteSteeringProfileRepository(path)
    repository.initialize()
    return repository, BUILT_IN_STEERING_CURVE


@pytest.fixture(params=[_button, _steering], ids=["button", "steering"])
def repository_and_definition(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[Any, Any]:
    return request.param(tmp_path / "app.sqlite")


def test_both_tables_share_one_implementation() -> None:
    assert issubclass(SqliteButtonProfileRepository, SqliteRevisionedProfileRepository)
    assert issubclass(SqliteSteeringProfileRepository, SqliteRevisionedProfileRepository)


def test_optimistic_concurrency_behaves_identically_on_every_table(
    repository_and_definition: tuple[Any, Any],
) -> None:
    repository, definition = repository_and_definition
    created = repository.create_profile("Track", definition)
    updated = repository.update_profile(created.profile_id, created.revision, "Rally", definition)

    assert updated.revision == created.revision + 1
    with pytest.raises(ProfileRevisionConflictError) as conflict:
        repository.update_profile(created.profile_id, created.revision, "Rally", definition)
    assert conflict.value.actual_revision == updated.revision
    with pytest.raises(ProfileNameConflictError):
        repository.create_profile("rally", definition)  # names are case-insensitive
    with pytest.raises(ProfileNotFoundError):
        repository.delete_profile(MISSING_ID, 1)


@pytest.mark.parametrize("revision", [None, 0, -1, True, "1", 1.0])
def test_storage_writes_require_a_concrete_positive_revision(
    repository_and_definition: tuple[Any, Any], revision: object
) -> None:
    repository, definition = repository_and_definition
    created = repository.create_profile("Track", definition)

    with pytest.raises(ValueError, match="expected_revision must be a positive integer"):
        repository.update_profile(created.profile_id, revision, "Rally", definition)
    with pytest.raises(ValueError, match="expected_revision must be a positive integer"):
        repository.delete_profile(created.profile_id, revision)


def test_revision_rules_differ_only_over_none() -> None:
    """``None`` means 'not from storage', which storage preconditions may never say."""

    validate_saved_profile_revision(None)
    with pytest.raises(ValueError, match="expected_revision must be a positive integer"):
        validate_expected_revision(None)
    for rejected in (0, -1, True, "1"):
        with pytest.raises(ValueError):
            validate_saved_profile_revision(rejected)  # type: ignore[arg-type]


def test_spec_refuses_a_table_name_it_would_have_to_quote() -> None:
    # The table name is interpolated into SQL, so the spec is the place that guarantees
    # it is a bare identifier rather than caller-controlled text.
    with pytest.raises(ValueError, match="bare SQL identifier"):
        RevisionedProfileSpec(
            kind="button profile",
            table="button_profiles; DROP TABLE steering_profiles",
            encode=lambda definition: b"",
            decode=lambda value: value,
            fingerprint=lambda definition: "",
            validate_name=lambda name: None,
            build=lambda *arguments: arguments,
        )

from typing import Any

from pydantic import Field


def omittable(**field_kwargs: Any) -> Any:
    """A field that may be left out, but never sent as null.

    Partial-update schemas need every field to be optional, but the columns
    behind them are ``NOT NULL`` — so accepting an explicit null would turn a
    client mistake into an IntegrityError. Pairing a non-optional annotation
    with an unvalidated ``None`` default makes null a 422 while still letting
    ``exclude_unset`` tell "omitted" apart from "set".

    The return type is ``Any`` so the ``None`` default type-checks against the
    non-optional annotation it is assigned to.
    """
    return Field(default=None, **field_kwargs)


def omittable_str(max_length: int) -> Any:
    """An omittable, never-null string field. See :func:`omittable`."""
    return omittable(max_length=max_length)

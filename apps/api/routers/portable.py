"""Importing and exporting a library's sections as one JSON document.

See ``schemas.portable`` for the format. ``/library/schema`` serves it as JSON
Schema, which is the thing to hand a model asked to write one of these files.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status

from deps.auth import CurrentUser
from deps.db import Db
from schemas.portable import ImportSummary, PortableLibrary
from services.portable import export_library, import_library
from services.sync_apply import UnapplicableChange

router = APIRouter(prefix="/library", tags=["Library"])

EXPORT_FILENAME = "resume-builder-library.json"


@router.post("/import", response_model=ImportSummary)
def import_portable_library(
    library: PortableLibrary,
    current_user: CurrentUser,
    db: Db,
    dry_run: bool = False,
) -> ImportSummary:
    """Add every section in the file, or nothing if any of it is invalid.

    Always adds: nothing already in the library is changed, and no resume is
    made — people build those from the sections in the app. With
    `dry_run=true` the file is checked and the summary returned, but nothing is
    kept.
    """
    try:
        return import_library(db, current_user.id, library, dry_run=dry_run)
    except UnapplicableChange as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


@router.get("/export", response_model=PortableLibrary)
def export_portable_library(
    current_user: CurrentUser, db: Db, response: Response
) -> PortableLibrary:
    """Everything the caller has, in the format import reads."""
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{EXPORT_FILENAME}"'
    )
    return export_library(db, current_user.id)


@router.get("/schema")
def portable_library_schema() -> dict[str, Any]:
    """The import format as JSON Schema."""
    return PortableLibrary.model_json_schema()

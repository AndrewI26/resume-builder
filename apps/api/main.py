from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from config import get_settings
from routers.auth import router as auth_router
from routers.education import router as education_router
from routers.experience import router as experience_router
from routers.google_auth import router as google_auth_router
from routers.personal_info import router as personal_info_router
from routers.project import router as project_router
from routers.resume import router as resume_router
from routers.skill import router as skill_router
from services.sidecar_guard import sidecar_token_guard

settings = get_settings()


def operation_id(route: APIRoute) -> str:
    return route.name


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """A local install has to prepare its own database; a hosted one is given one."""
    if settings.is_local:
        # imported here rather than at module scope: it pulls in alembic, which
        # the hosted API has no reason to load into every process
        from deps.db import engine
        from services.local_bootstrap import bootstrap_local_database

        bootstrap_local_database(engine)

    yield


app = FastAPI(generate_unique_id_function=operation_id, lifespan=lifespan)

# Added before CORS so that CORS ends up the outer layer: middleware added
# later wraps what came before it, and a preflight has to be answered by CORS
# rather than turned away for carrying no token it was still asking to send.
if settings.is_local and settings.sidecar_token:
    app.middleware("http")(sidecar_token_guard(settings.sidecar_token))


def _allowed_origins() -> list[str]:
    """Who may call this API from a browser.

    A local install is reached from the desktop app's own window, which is not
    served over http and so has no origin the API could be told to expect. It
    is also bound to loopback and gated by a secret the shell generates per
    run, which is the actual boundary here — CORS is not what keeps anything
    out on one person's machine.
    """
    if settings.is_local or settings.node_env == "development":
        return ["*"]

    return [settings.frontend_url]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(education_router)
app.include_router(experience_router)
app.include_router(google_auth_router)
app.include_router(personal_info_router)
app.include_router(project_router)
app.include_router(resume_router)
app.include_router(skill_router)

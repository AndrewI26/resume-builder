from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from config import get_settings
from deps.notify import PdfNotifier
from routers.auth import router as auth_router
from routers.education import router as education_router
from routers.experience import router as experience_router
from routers.google_auth import router as google_auth_router
from routers.personal_info import router as personal_info_router
from routers.portable import router as portable_router
from routers.project import router as project_router
from routers.resume import router as resume_router
from routers.skill import router as skill_router
from services.pdf_worker import run_pool

settings = get_settings()


def operation_id(route: APIRoute) -> str:
    return route.name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start the PDF listener before the first request.

    The API never compiles: ``worker.py`` claims and runs the jobs, and reaps
    the queue. What the API still needs is the listener, because a request
    waiting here has to hear that its job finished in the worker process.
    """
    notifier = PdfNotifier()
    app.state.pdf_notifier = notifier

    async with run_pool(notifier, 0, reap=False):
        yield


# The interactive docs are a development tool. The schema itself stays up:
# codegen reads it, and docker-compose.yml's healthcheck polls it.
_docs_enabled = settings.node_env == "development"

app = FastAPI(
    generate_unique_id_function=operation_id,
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
)


def _allowed_origins() -> list[str]:
    """Who may call this API from a browser."""
    if settings.node_env == "development":
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
app.include_router(portable_router)
app.include_router(project_router)
app.include_router(resume_router)
app.include_router(skill_router)

from collections.abc import AsyncIterator
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
from routers.project import router as project_router
from routers.resume import router as resume_router
from routers.skill import router as skill_router
from services.pdf_worker import run_pool

settings = get_settings()


def operation_id(route: APIRoute) -> str:
    return route.name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Bring up the PDF queue alongside the API.

    The workers live in this process, so how many there are is a property of
    how the API was started: ``PDF_WORKER_COUNT=6 bun run dev:api``. Zero is a
    real answer — it is what the compose deployment sets, where a worker
    container claims the jobs instead — and the listener still runs, because a
    request waiting here has to hear that its job finished wherever it ran.
    """
    notifier = PdfNotifier()
    app.state.pdf_notifier = notifier

    async with run_pool(notifier, settings.pdf_worker_count):
        yield


app = FastAPI(generate_unique_id_function=operation_id, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*" if settings.node_env == "development" else settings.frontend_url
    ],
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

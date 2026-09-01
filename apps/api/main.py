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

settings = get_settings()


def operation_id(route: APIRoute) -> str:
    return route.name


app = FastAPI(generate_unique_id_function=operation_id)

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

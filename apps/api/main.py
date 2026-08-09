from fastapi import FastAPI

from routers.auth import router as auth_router
from routers.experience import router as experience_router
from routers.project import router as project_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(experience_router)
app.include_router(project_router)

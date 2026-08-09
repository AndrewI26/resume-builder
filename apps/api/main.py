from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import router as auth_router
from routers.experience import router as experience_router
from routers.google_auth import router as google_auth_router
from settings import get_settings

settings = get_settings()

app = FastAPI()

# the frontend is on a different origin and auth rides on a cookie, so it needs
# both an explicit origin and credentials allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(google_auth_router)
app.include_router(experience_router)

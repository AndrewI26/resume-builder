from fastapi import FastAPI
from routers.experience import router as experience_router

app = FastAPI()

app.include_router(experience_router)

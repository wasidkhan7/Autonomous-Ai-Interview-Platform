from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.db.session import engine, Base
from app.api import candidates

from app.api import evaluation

from app.api import interviews

from app.api import voice_interview

from app.api import analytics


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: nothing to clean up yet


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# Add this route to fix the 404 error
@app.get("/")
def read_root():
    return {"message": "Welcome to my FastAPI application!"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(candidates.router)

app.include_router(interviews.router)

app.include_router(evaluation.router)

app.include_router(voice_interview.router)

app.include_router(analytics.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
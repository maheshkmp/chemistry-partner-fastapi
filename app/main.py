from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import papers, users, auth
from .database import Base, engine

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(papers.router, prefix="/papers", tags=["papers"])

# Create database tables
Base.metadata.create_all(bind=engine)
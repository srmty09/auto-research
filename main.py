from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import auth, agent, sessions, files

Base.metadata.create_all(bind=engine)

AVAILABLE_MODELS = [
    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "provider": "Groq"},
    {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant", "provider": "Groq"},
    {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B 32K", "provider": "Groq"},
]

app = FastAPI(title="Auto Research")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(files.router, prefix="/api/files", tags=["files"])


@app.get("/api/models")
def get_models():
    return AVAILABLE_MODELS


app.mount("/", StaticFiles(directory="static", html=True), name="static")

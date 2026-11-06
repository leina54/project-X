from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import auth, inventory, matching, payments, shops
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Software X",
    description="Real-time local inventory matching engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


app.include_router(auth.router)
app.include_router(shops.router)
app.include_router(inventory.router)
app.include_router(matching.router)
app.include_router(payments.router)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.environment,
        "supabase": settings.supabase_configured,
        "maps": settings.maps_configured,
        "llm": settings.llm_provider or "offline",
    }

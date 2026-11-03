"""RouteWise API.

Start it from the project root:
    uvicorn app.main:app --app-dir backend
Interactive docs: http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_analyze, routes_execute, routes_metrics, routes_settings
from app.models.api_models import HealthResponse
from app.providers.errors import ProviderError
from app.state import AppState, build_default_state

DESCRIPTION = (
    "Explainable dynamic LLM task routing. An experimental, local, educational prototype: "
    "the router does not guarantee correctness, and validation does not prove factual "
    "correctness. Estimated costs depend on the configured prices."
)


def create_app(state: AppState | None = None) -> FastAPI:
    app = FastAPI(title="RouteWise", version="0.1.0", description=DESCRIPTION)
    app.state.rw = state or build_default_state()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                       "http://localhost:8501", "http://127.0.0.1:8501"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, error: ProviderError):
        return JSONResponse(status_code=502, content={"detail": str(error)})

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health(request: Request):
        info = request.app.state.rw.provider.get_model_info()
        return HealthResponse(status="ok", provider=info.provider, provider_mode=info.mode)

    for module in (routes_analyze, routes_execute, routes_metrics, routes_settings):
        app.include_router(module.router)
    return app


app = create_app()
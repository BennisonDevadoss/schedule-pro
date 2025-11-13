from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .settings import SETTINGS


def configure_cors(app_: FastAPI) -> None:
    # Support multiple origins separated by comma, or single origin
    origins = [origin.strip() for origin in SETTINGS.ALLOWED_ORIGIN.split(",")]
    
    app_.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
        expose_headers=["Authorization"],
    )

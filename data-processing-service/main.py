from fastapi import FastAPI

from infrastructure.adapters.input.api.routes import router


app = FastAPI(
    title="Green AI - Data Processing Service",
    description=(
        "Microservicio encargado del procesamiento "
        "y preparación de métricas de infraestructura "
        "para el proyecto Green AI."
    ),
    version="1.0.0",
)


app.include_router(
    router,
    prefix="/api/v1",
)


@app.get(
    "/",
    tags=["Root"],
)
def root():
    return {
        "service": "Green AI - Data Processing Service",
        "version": "1.0.0",
        "docs": "/docs",
    }
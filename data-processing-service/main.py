from contextlib import asynccontextmanager
import re
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from domain.errors import ServiceError
from infrastructure.settings import Settings
from infrastructure.adapters.input.api.routes import router


@asynccontextmanager
async def lifespan(app):
    app.state.settings = Settings.from_env()
    yield


app = FastAPI(title="Green AI - Data Processing Service", version="1.1.0",
    description="Históricos de Monitoring y Supabase separados; preparación provisional para Prediction. Servicio interno detrás del Gateway.",
    lifespan=lifespan)


def problem(request, status, code, detail):
    return JSONResponse(status_code=status, media_type="application/problem+json", content={
        "type": "about:blank", "title": code, "status": status, "detail": detail,
        "instance": request.url.path, "code": code, "requestId": request.state.request_id,
    }, headers={"X-Request-Id": request.state.request_id})


@app.middleware("http")
async def correlation(request: Request, call_next):
    received = request.headers.get("X-Request-Id", "")
    request.state.request_id = received if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", received) else str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response


@app.exception_handler(ServiceError)
async def source_error(request, exc):
    return problem(request, exc.status, exc.code, str(exc))


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Do not echo raw inputs (headers, cursor or arbitrary injected values).
    fields = sorted({str(e["loc"][-1]) for e in exc.errors()})
    return problem(request, 422, "INVALID_QUERY", "Revise los parámetros: " + ", ".join(fields))


app.include_router(router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    return problem(request, 500, "INTERNAL_ERROR", "No fue posible completar la operación.")


@app.get("/", tags=["Root"])
def root():
    return {"service": "Green AI - Data Processing Service", "version": "1.1.0", "docs": "/docs"}

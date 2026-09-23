from fastapi import APIRouter


router = APIRouter()


@router.get(
    "/health",
    tags=["Health"],
    summary="Verificar estado del servicio",
)
def health_check():
    """
    Comprueba que el Data Processing Service
    se encuentra disponible.
    """

    return {
        "status": "healthy",
        "service": "data-processing-service",
        "project": "Green AI",
    }
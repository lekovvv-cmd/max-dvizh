"""Small set of stable domain error codes exposed to the Mini App."""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class DomainError(HTTPException):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def domain_error_response(_request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, DomainError)
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "detail": error.detail},
    )

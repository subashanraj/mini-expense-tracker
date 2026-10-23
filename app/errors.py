"""Every error leaves the API as {"error": "message"}.

Internal details (SQL, driver messages, stack traces) are logged server-side
and never sent to the client.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

DATABASE_ERROR = "A database error occurred. Please try again."
INTERNAL_ERROR = "Internal server error"


class ApiError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


def first_message(errors: list[dict]) -> str:
    error = errors[0]
    if error["type"] == "json_invalid":
        return "Request body must be valid JSON"
    if error["type"] == "invalid":  # our PydanticCustomError: message is already user-facing
        return error["msg"]
    field = ".".join(str(part) for part in error.get("loc", ()) if part not in ("body", "query"))
    return f"{field}: {error['msg']}" if field else error["msg"]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.message)

    @app.exception_handler(ValidationError)
    async def handle_validation_error(_: Request, exc: ValidationError) -> JSONResponse:
        return error_response(400, first_message(exc.errors()))

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI's default is 422; the assessment requires 400 for bad input.
        return error_response(400, first_message(list(exc.errors())))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error_response(exc.status_code, str(exc.detail))

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database error on %s %s", request.method, request.url.path)
        return error_response(500, DATABASE_ERROR)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return error_response(500, INTERNAL_ERROR)

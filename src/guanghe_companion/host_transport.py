import asyncio
from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field

from .host_auth import AuthenticationError
from .dialogue import MAX_DIALOGUE_INPUT_LENGTH
from .emotional_memory import MAX_MEMORY_TEXT_LENGTH, MAX_MEMORY_TITLE_LENGTH
from .host_service import CompanionHost, HostError


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PairBody(StrictBody):
    invitation: str = Field(min_length=32, max_length=128)
    device_name: str = Field(min_length=1, max_length=80)


class VersionedBody(StrictBody):
    session_id: str = Field(min_length=1, max_length=64)
    expected_epoch: int = Field(ge=0)
    expected_revision: int = Field(ge=1)
    request_id: str = Field(min_length=1, max_length=128)


class MessageBody(VersionedBody):
    text: str = Field(min_length=1, max_length=MAX_DIALOGUE_INPUT_LENGTH)


class MemoryBody(VersionedBody):
    operation: Literal["remember", "confirm", "correct", "forget"]
    text: str = Field(default="", max_length=MAX_MEMORY_TEXT_LENGTH)
    title: str = Field(default="", max_length=MAX_MEMORY_TITLE_LENGTH)
    memory_id: str = Field(default="", max_length=128)
    pending_id: str = Field(default="", max_length=128)


def create_host_app(host: CompanionHost) -> FastAPI:
    app = FastAPI(title="E-Moti Host", version="1.0.0", docs_url=None, redoc_url=None)
    bearer = HTTPBearer(auto_error=False)

    async def token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None:
            raise HostError("unauthorized", "bearer device credential required", 401)
        return credentials.credentials

    async def command(credential, action, payload=None):
        return await asyncio.wrap_future(host.submit(credential, action, payload))

    @app.middleware("http")
    async def bounded_request(request: Request, call_next):
        if request.method == "POST":
            content = bytearray()
            async for chunk in request.stream():
                content.extend(chunk)
                if len(content) > 16384:
                    return JSONResponse({"error": {"code": "body_too_large"}}, status_code=413)
            request._body = bytes(content)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HostError)
    async def host_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"error": {"code": "invalid_request", "message": "request fields are invalid"}}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing_error(request, exc):
        return JSONResponse({"error": {"code": "not_found", "message": "requested record does not exist"}}, status_code=404)

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"error": {"code": "invalid_operation", "message": "operation rejected"}}, status_code=400)

    @app.exception_handler(RuntimeError)
    async def busy_error(request, exc):
        return JSONResponse({"error": {"code": type(exc).__name__, "message": "host operation unavailable"}}, status_code=409)

    @app.post("/v1/pair")
    async def pair(body: PairBody):
        try:
            return host.credentials.pair(body.invitation, device_name=body.device_name)
        except AuthenticationError as exc:
            raise HostError("invalid_invitation", "pairing invitation expired or already used", 401) from exc

    @app.get("/v1/session")
    async def session(credential=Depends(token)):
        return await command(credential, "session")

    @app.get("/v1/events")
    async def events(after: int = 0, credential=Depends(token)):
        return await command(credential, "events", {"after": after})

    @app.get("/v1/memory")
    async def memory(credential=Depends(token)):
        return await command(credential, "memory")

    @app.get("/v1/memory/{memory_id}/source")
    async def source(memory_id: str, credential=Depends(token)):
        return await command(credential, "source", {"memory_id": memory_id})

    @app.post("/v1/memory")
    async def edit_memory(body: MemoryBody, credential=Depends(token)):
        return await command(credential, "memory_edit", body.model_dump())

    @app.post("/v1/messages", status_code=202)
    async def message(body: MessageBody, credential=Depends(token)):
        return await command(credential, "message", body.model_dump())

    @app.get("/v1/messages/{request_id}")
    async def message_result(request_id: str, credential=Depends(token)):
        return await command(credential, "message_result", {"request_id": request_id})

    @app.post("/v1/cancel")
    async def cancel(body: VersionedBody, credential=Depends(token)):
        return await command(credential, "cancel", body.model_dump())

    return app

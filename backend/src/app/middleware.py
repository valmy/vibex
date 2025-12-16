from typing import Callable, Awaitable
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .core.security import credentials_exception, verify_token
from .db.session import get_sync_engine
from .models.account import User


class AdminOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.method in ["POST", "PUT", "DELETE"]:
            # A list of routes that are exempt from the admin check
            exempt_routes = ["/api/v1/auth/login", "/api/v1/auth/challenge"]

            # Account management routes handle their own ownership control
            # so they don't need admin-only restriction
            if request.url.path.startswith("/api/v1/accounts"):
                return await call_next(request)

            if request.url.path in exempt_routes:
                return await call_next(request)

            token = request.headers.get("Authorization")
            if not token:
                return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

            if token.startswith("Bearer "):
                token = token.split("Bearer ")[1]

            try:
                token_data = verify_token(token, credentials_exception)
                # Create a sync engine and session for this check
                engine = get_sync_engine()
                SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                db = SessionLocal()
                user = (
                    db.query(User)
                    .filter(func.lower(User.address) == func.lower(token_data.username))
                    .first()
                )
                db.close()
                if not user or not user.is_admin:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "The user doesn't have enough privileges"},
                    )
            except HTTPException as e:
                return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

        response = await call_next(request)
        return response

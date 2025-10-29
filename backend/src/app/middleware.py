from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from .core.security import verify_token, credentials_exception
from .db.session import get_sync_engine
from .models.account import User


class AdminOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ["POST", "PUT"]:
            # A list of routes that are exempt from the admin check
            exempt_routes = ["/api/v1/auth/login", "/api/v1/auth/challenge"]
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
                user = db.query(User).filter(User.address == token_data.username).first()
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

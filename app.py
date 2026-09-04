import os
from pathlib import Path
import traceback
import uvicorn
import uuid

from fastapi import Depends, HTTPException
from fastapi.responses import RedirectResponse
from src.utils.auth import hash_password, verify_password, sign_token, verify_token
from src.clients.migrations import run_migrations

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.api.sessions import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    clear_credentials,
    get_credentials_for,
    new_session_id,
    store_credentials,
)
from src.api.validation import check_database_url, check_groq_api_key
from src.clients import cache
from src.config.session import (
    MissingCredentialsError,
    credential_status,
    use_credentials,
    require,
)
from src.clients.checkpointer import get_session_checkpointer, get_connection
from src.config.session import resolve_database_url
from src.config.settings import COOKIE_SAMESITE, COOKIE_SECURE, CORS_ORIGINS
from src.graph.runner import run_travel_agent

# This is to allow nested event loops for async calls in FastAPI
import nest_asyncio
nest_asyncio.apply()


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="TravelBrain AI",
    description="LangGraph Multi-Agent Travel Planner with FastAPI Frontend",
    version="1.0.0"
)


# Only needed when the browser talks to this API on a different origin. With
# the Vercel rewrite the frontend is same-origin, so this stays inactive.
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )


app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR / "static")),
    name="static"
)


templates = Jinja2Templates(
    directory=str(FRONTEND_DIR / "templates")
)



class TravelRequest(BaseModel):
    message: str
    thread_id: str | None = None


class AuthRequest(BaseModel):
    email: str
    password: str


@app.on_event("startup")
async def startup_event():
    from src.config import settings
    url = settings.DATABASE_URL
    if url:
        try:
            run_migrations(settings.normalize_database_url(url))
        except Exception as e:
            print(f"Startup migration failed: {str(e)}")


def get_current_user_optional(request: Request) -> dict | None:
    token = request.cookies.get("travelbrain_auth")
    if not token:
        return None
    return verify_token(token)


def get_current_user(request: Request) -> dict:
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


class ConfigRequest(BaseModel):
    """
    None leaves a field untouched, "" clears it. Keys are held in server
    memory for this session only and are never echoed back.
    """

    groq_api_key: str | None = None
    database_url: str | None = None



def _session_id(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
    )



@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user": user}
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={}
    )


# =========================
# Authentication APIs
# =========================

@app.post("/api/auth/register")
async def register(body: AuthRequest, request: Request):
    email = body.email.strip().lower()
    password = body.password
    
    if not email or not password:
        return JSONResponse(status_code=400, content={"success": False, "error": "Email and password are required"})
        
    try:
        from src.config import settings
        from src.clients.checkpointer import get_connection
        
        url = settings.DATABASE_URL
        if not url:
            return JSONResponse(status_code=400, content={"success": False, "error": "Database is not configured on the server."})
            
        conn = get_connection(settings.normalize_database_url(url))
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            if cur.fetchone():
                return JSONResponse(status_code=400, content={"success": False, "error": "Email is already registered."})
                
            pw_hash = hash_password(password)
            cur.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id;", (email, pw_hash))
            user_id = cur.fetchone()["id"]
            
        return JSONResponse(content={"success": True, "message": "User registered successfully."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.post("/api/auth/login")
async def login(body: AuthRequest, response: Response):
    email = body.email.strip().lower()
    password = body.password
    
    try:
        from src.config import settings
        from src.clients.checkpointer import get_connection
        
        url = settings.DATABASE_URL
        if not url:
            return JSONResponse(status_code=500, content={"success": False, "error": "Database is not configured on the server."})
            
        conn = get_connection(settings.normalize_database_url(url))
        with conn.cursor() as cur:
            cur.execute("SELECT id, password_hash FROM users WHERE email = %s;", (email,))
            user = cur.fetchone()
            
        if not user or not verify_password(password, user["password_hash"]):
            return JSONResponse(status_code=400, content={"success": False, "error": "Invalid email or password."})
            
        payload = {"user_id": user["id"], "email": email}
        token = sign_token(payload)
        
        response.set_cookie(
            "travelbrain_auth",
            token,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            samesite=COOKIE_SAMESITE,
            secure=COOKIE_SECURE,
        )
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.post("/api/auth/logout")
async def logout(response: Response):
    response.delete_cookie("travelbrain_auth")
    return {"success": True}


# =========================
# Credentials
# =========================

@app.get("/api/config")
async def read_config(request: Request):
    """What is configured, and where it came from. Never returns a secret."""

    credentials = get_credentials_for(_session_id(request))

    with use_credentials(credentials):
        return JSONResponse(content=credential_status())


@app.post("/api/config")
async def write_config(request: Request, body: ConfigRequest):
    """
    Store credentials for this browser session. Each supplied value is
    checked against the real service before being accepted.
    """

    session_id = _session_id(request) or new_session_id()

    errors = {}

    groq_key = (body.groq_api_key or "").strip()
    if groq_key:
        ok, detail = check_groq_api_key(groq_key)
        if not ok:
            errors["groq_api_key"] = detail

    database_url = (body.database_url or "").strip()
    if database_url:
        ok, detail = check_database_url(database_url)
        if not ok:
            errors["database_url"] = detail

    if errors:
        response = JSONResponse(
            status_code=400,
            content={"success": False, "errors": errors},
        )
        _set_session_cookie(response, session_id)
        return response

    credentials = store_credentials(
        session_id,
        groq_api_key=body.groq_api_key,
        database_url=body.database_url,
    )

    with use_credentials(credentials):
        payload = {"success": True, **credential_status()}

    response = JSONResponse(content=payload)
    _set_session_cookie(response, session_id)

    return response


@app.delete("/api/config")
async def reset_config(request: Request):
    """Drop session keys and fall back to whatever the server's .env has."""

    clear_credentials(_session_id(request))

    with use_credentials(None):
        return JSONResponse(content={"success": True, **credential_status()})


# =========================
# Planning
# =========================

@app.post("/api/travel")
async def travel_planner(request: Request, request_data: TravelRequest):
    user = get_current_user(request)
    user_id = user["user_id"]
    credentials = get_credentials_for(_session_id(request))

    try:
        user_message = request_data.message.strip()

        if not user_message:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Message cannot be empty."
                }
            )

        thread_id = request_data.thread_id
        prefix = f"usr_{user_id}_"
        if thread_id:
            if not thread_id.startswith(prefix):
                return JSONResponse(status_code=403, content={"success": False, "error": "Access Denied"})
        else:
            thread_id = f"{prefix}{uuid.uuid4().hex}"

        with use_credentials(credentials):
            result = run_travel_agent(
                user_input=user_message,
                thread_id=thread_id
            )

        return JSONResponse(
            content={
                "success": True,
                "thread_id": result["thread_id"],
                "answer": result["answer"],
                "flight_results": result["flight_results"],
                "hotel_results": result["hotel_results"],
                "weather_results": result.get("weather_results", ""),
                "itinerary": result["itinerary"],
                "llm_calls": result["llm_calls"],
            }
        )

    except MissingCredentialsError as e:
        # The frontend turns this into a prompt to open Settings.
        return JSONResponse(
            status_code=428,
            content={
                "success": False,
                "error": str(e),
                "missing": e.missing,
            }
        )

    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )



# =========================
# History / Previous Trips
# =========================

@app.get("/api/history")
async def get_history(request: Request):
    """Retrieve all unique conversation threads from the checkpointer scoped to the authenticated user."""
    user = get_current_user(request)
    user_id = user["user_id"]
    prefix = f"usr_{user_id}_"
    credentials = get_credentials_for(_session_id(request))

    with use_credentials(credentials):
        try:
            require("DATABASE_URL")
            checkpointer = get_session_checkpointer()
            # Fetch all checkpoints to group by thread_id
            configs = list(checkpointer.list(None))
            
            threads = {}
            for tup in configs:
                thread_id = tup.config["configurable"]["thread_id"]
                
                # Check is user's thread
                if not thread_id.startswith(prefix):
                    continue
                
                checkpoint_ns = tup.config["configurable"].get("checkpoint_ns", "")
                if checkpoint_ns != "":
                    continue
                
                step = tup.metadata.get("step", -1)
                
                # Overwrite if we find a later step (latest checkpoint for the thread)
                if thread_id not in threads or step > threads[thread_id]["step"]:
                    channel_values = tup.checkpoint.get("channel_values", {}) if tup.checkpoint else {}
                    user_query = channel_values.get("user_query", "")
                    
                    title = "New Trip"
                    if user_query:
                        title = user_query.strip()
                    else:
                        messages = channel_values.get("messages", [])
                        if messages:
                            title = getattr(messages[0], "content", str(messages[0])).strip()
                    
                    # Clean/trim title
                    if len(title) > 50:
                        title = title[:47] + "..."
                        
                    ts = tup.checkpoint.get("ts") if tup.checkpoint else None
                    
                    threads[thread_id] = {
                        "thread_id": thread_id,
                        "title": title,
                        "step": step,
                        "created_at": ts
                    }
            
            # Sort threads by recency (created_at desc)
            sorted_threads = sorted(threads.values(), key=lambda t: t.get("created_at") or "", reverse=True)
            return JSONResponse(content={"success": True, "threads": sorted_threads})

        except MissingCredentialsError as e:
            return JSONResponse(
                status_code=428,
                content={
                    "success": False,
                    "error": str(e),
                    "missing": e.missing,
                }
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": str(e)
                }
            )


@app.get("/api/history/{thread_id}")
async def get_history_detail(request: Request, thread_id: str):
    """Retrieve details for a specific thread_id scoped to the authenticated user."""
    user = get_current_user(request)
    user_id = user["user_id"]
    prefix = f"usr_{user_id}_"
    
    if not thread_id.startswith(prefix):
        return JSONResponse(status_code=403, content={"success": False, "error": "Access Denied"})
        
    credentials = get_credentials_for(_session_id(request))

    with use_credentials(credentials):
        try:
            require("DATABASE_URL")
            checkpointer = get_session_checkpointer()
            # Fetch latest checkpoint tuple for the thread
            config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
            tup = checkpointer.get_tuple(config)
            
            if not tup:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "error": f"Thread {thread_id} not found."}
                )
                
            channel_values = tup.checkpoint.get("channel_values", {}) if tup.checkpoint else {}
            
            answer = ""
            messages = channel_values.get("messages", [])
            if messages:
                answer = getattr(messages[-1], "content", str(messages[-1]))
                
            return JSONResponse(
                content={
                    "success": True,
                    "thread_id": thread_id,
                    "answer": answer,
                    "flight_results": channel_values.get("flight_results", ""),
                    "hotel_results": channel_values.get("hotel_results", ""),
                    "weather_results": channel_values.get("weather_results", ""),
                    "itinerary": channel_values.get("itinerary", ""),
                    "llm_calls": channel_values.get("llm_calls", 0),
                    "user_query": channel_values.get("user_query", ""),
                }
            )

        except MissingCredentialsError as e:
            return JSONResponse(
                status_code=428,
                content={
                    "success": False,
                    "error": str(e),
                    "missing": e.missing,
                }
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": str(e)
                }
            )


@app.delete("/api/history/{thread_id}")
async def delete_history(request: Request, thread_id: str):
    """Delete a thread and all of its checkpoints if owned by the user."""
    user = get_current_user(request)
    user_id = user["user_id"]
    prefix = f"usr_{user_id}_"
    
    if not thread_id.startswith(prefix):
        return JSONResponse(status_code=403, content={"success": False, "error": "Access Denied"})
        
    credentials = get_credentials_for(_session_id(request))

    with use_credentials(credentials):
        try:
            require("DATABASE_URL")
            conn = get_connection(resolve_database_url())
            
            with conn.cursor() as cur:
                cur.execute("DELETE FROM checkpoints WHERE thread_id = %s;", (thread_id,))
                cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s;", (thread_id,))
                cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s;", (thread_id,))
                
            return JSONResponse(content={"success": True})

        except MissingCredentialsError as e:
            return JSONResponse(
                status_code=428,
                content={
                    "success": False,
                    "error": str(e),
                    "missing": e.missing,
                }
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": str(e)
                }
            )



@app.head("/", include_in_schema=False)
async def home_head():
    """Hosting platforms probe with HEAD to detect an open port."""

    return Response(status_code=200)


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check(request: Request):
    credentials = get_credentials_for(_session_id(request))

    with use_credentials(credentials):
        status = credential_status()

    return {
        "status": "ok",
        "message": "AI Travel Planner API is running",
        "ready": status["ready"],
        "missing": status["missing"],
        "cache": cache.status(),
    }


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={})



if __name__ == "__main__":
    # Defaults suit local development. In Docker, HOST is set to 0.0.0.0
    # so the port is reachable from outside the container.
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "true").lower() not in ("false", "0", "no")
    )

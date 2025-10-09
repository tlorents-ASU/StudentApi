# # routes/auth.py
# from fastapi import APIRouter
# from fastapi.responses import RedirectResponse, PlainTextResponse, JSONResponse
# from itsdangerous import URLSafeSerializer
# import os, time
#
# router = APIRouter()
#
# SECRET_KEY = os.getenv("SECRET_KEY", "devsecret")
# s = URLSafeSerializer(SECRET_KEY, salt="auth")
#
# @router.get("/ping")
# def ping():
#     return PlainTextResponse("pong")
#
# @router.get("/dev-login-no-redirect")
# def dev_login_no_redirect():
#     """Set cookie and return JSON (no redirect) to prove the cookie gets set."""
#     cookie_val = s.dumps({"asurite": "tlorents", "ts": int(time.time())})
#     resp = JSONResponse({"ok": True})
#     resp.set_cookie("auth", cookie_val, httponly=True, secure=False, samesite="lax", path="/")
#     return resp
#
# @router.get("/dev-login")
# def dev_login():
#     cookie_val = s.dumps({"asurite": "tlorents", "ts": int(time.time())})
#     resp = RedirectResponse(url="http://localhost:3000/")  # keep localhost for this plan
#     resp.set_cookie("auth", cookie_val, httponly=True, secure=False, samesite="lax", path="/")
#     return resp
#
# @router.get("/user")
# def user():
#     return {"asurite": "tlorents", "is_admin": True, "role": "admin"}


# routes/auth.py  (DEV auth + /user)
from fastapi import APIRouter, Response, Depends, Request, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from database import get_db
from models.user_access import UserAccess
from utils.rbac import merged_perms

router = APIRouter()

@router.get("/ping")
def ping():
    return PlainTextResponse("pong")

@router.get("/dev-impersonate")
def dev_impersonate(asurite: str, response: Response, db: Session = Depends(get_db)):
    """
    DEV ONLY: set a plain-text cookie 'auth' = asurite for impersonation.
    In PROD you'll swap this out for CAS and a signed cookie.
    """
    asurite = asurite.lower().strip()
    # Optional: validate exists
    # if not db.get(UserAccess, asurite):
    #     raise HTTPException(status_code=404, detail="No such user")
    response.set_cookie("auth", asurite, httponly=True, samesite="lax", secure=False, path="/")
    return {"ok": True, "asurite": asurite}

# ---- NEW: pure dependency you can reuse anywhere ----
def current_user(request: Request, db: Session = Depends(get_db)) -> dict:
    """
    Resolve the current user from the 'auth' cookie (DEV),
    and return the shape your frontend expects.
    """
    asurite = (request.cookies.get("auth") or "").lower().strip()
    if not asurite:
        return {"asurite": None, "role": "guest", "is_admin": False, "perms": {}}

    row = db.get(UserAccess, asurite)
    if not row:
        return {"asurite": asurite, "role": "guest", "is_admin": False, "perms": {}}

    flags = {
        "assignment_adder": bool(row.assignment_adder),
        "applications": bool(row.applications),
        "phd_applications": bool(row.phd_applications),
        "student_summary_page": bool(row.student_summary_page),
        "bulk_upload_assignments": bool(row.bulk_upload_assignments),
        "manage_assignments": bool(row.manage_assignments),
        "login": bool(row.login),
        "master_dashboard": bool(row.master_dashboard),
        "faculty_dashboard": bool(row.faculty_dashboard),
    }
    perms = merged_perms(row.role, flags)
    return {
        "asurite": row.asu_id,
        "role": row.role,
        "is_admin": row.role == "admin",
        "perms": perms,
    }

# Reuse the dependency for the public route
@router.get("/user")
def get_user(user: dict = Depends(current_user)):
    return user


# @router.get("/user")
# def get_user(request: Request, db: Session = Depends(get_db)):
#     """
#     Return the logged-in user based on the 'auth' cookie (plain ASURITE in dev).
#     Shape matches what your frontend expects.
#     """
#     asurite = (request.cookies.get("auth") or "").lower().strip()
#     if not asurite:
#         return {"asurite": None, "role": "guest", "is_admin": False, "perms": {}}
#
#     row = db.get(UserAccess, asurite)
#     if not row:
#         # Cookie present but no access row: treat as guest (or 404/403 if you prefer)
#         return {"asurite": asurite, "role": "guest", "is_admin": False, "perms": {}}
#
#     flags = {
#         "assignment_adder": bool(row.assignment_adder),
#         "applications": bool(row.applications),
#         "phd_applications": bool(row.phd_applications),
#         "student_summary_page": bool(row.student_summary_page),
#         "bulk_upload_assignments": bool(row.bulk_upload_assignments),
#         "manage_assignments": bool(row.manage_assignments),
#         "login": bool(row.login),
#         "master_dashboard": bool(row.master_dashboard),
#     }
#     perms = merged_perms(row.role, flags)
#     return {
#         "asurite": row.asu_id,
#         "role": row.role,
#         "is_admin": row.role == "admin",
#         "perms": perms,
#     }


@router.get("/dev-logout")
def dev_logout(response: Response):
    """DEV ONLY: clear the cookie."""
    response.delete_cookie("auth", path="/")
    return {"ok": True}
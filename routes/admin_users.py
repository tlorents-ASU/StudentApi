# from fastapi import APIRouter, Depends, HTTPException, Request
# from sqlalchemy.orm import Session
# from database import get_db
# from models.user_access import UserAccess
# from utils.rbac import ROLE_DEFAULTS, merged_perms
# from routes.auth import user as auth_user  # only if you need; not required here
#
# router = APIRouter(prefix="/api/admin", tags=["admin-users"])
#
# def require_admin(request: Request, db: Session = Depends(get_db)):
#     # DEV: trust 'tlorents' while you wire CAS/cookie
#     asurite = "tlorents"
#     # If you want to use the cookie now, replace with:
#     # from routes.auth import get_current_user
#     # asurite = get_current_user(request.cookies.get("auth"))
#
#     row = db.get(UserAccess, asurite)
#     if not row or row.role != "admin":
#         raise HTTPException(status_code=403, detail="forbidden")
#     return asurite
#
# @router.get("/users")
# def list_users(db: Session = Depends(get_db), me: str = Depends(require_admin)):
#     rows = db.query(UserAccess).all()
#     # include merged perms for convenience
#     return [r.__dict__ | {"_perms": merged_perms(r.role, r.__dict__)} for r in rows]
#
# @router.post("/users")
# def create_user(payload: dict, db: Session = Depends(get_db), me: str = Depends(require_admin)):
#     asu_id = payload["asu_id"].lower()
#     role = payload["role"]
#     if db.get(UserAccess, asu_id):
#         raise HTTPException(400, "asu_id exists")
#     r = UserAccess(
#         asu_id=asu_id,
#         role=role,
#         **{k: bool(payload.get(k, ROLE_DEFAULTS[role].get(k, 0)))
#            for k in ROLE_DEFAULTS["admin"].keys()}
#     )
#     db.add(r); db.commit(); db.refresh(r)
#     return r
#
# @router.patch("/users/{asu_id}")
# def update_user(asu_id: str, payload: dict, db: Session = Depends(get_db), me: str = Depends(require_admin)):
#     r = db.get(UserAccess, asu_id.lower())
#     if not r: raise HTTPException(404, "not found")
#     if "role" in payload: r.role = payload["role"]
#     for k in ROLE_DEFAULTS["admin"].keys():
#         if k in payload: setattr(r, k, bool(payload[k]))
#     db.commit(); db.refresh(r)
#     return r
#
# @router.delete("/users/{asu_id}")
# def delete_user(asu_id: str, db: Session = Depends(get_db), me: str = Depends(require_admin)):
#     r = db.get(UserAccess, asu_id.lower())
#     if not r: raise HTTPException(404, "not found")
#     db.delete(r); db.commit()
#     return {"ok": True}



# routes/admin_users.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from models.user_access import UserAccess
from utils.rbac import ROLE_DEFAULTS, merged_perms

router = APIRouter(prefix="/api/admin", tags=["admin-users"])

# def require_admin(request: Request, db: Session = Depends(get_db)):
#     # DEV: trust 'tlorents' while wiring CAS/cookie
#     asurite = "tlorents"
#     row = db.get(UserAccess, asurite)
#     if not row or row.role != "admin":
#         raise HTTPException(status_code=403, detail="forbidden")
#     return asurite

def require_admin(request: Request, db: Session = Depends(get_db)):
    asurite = (request.cookies.get("auth") or "").lower().strip()
    if not asurite:
        raise HTTPException(status_code=401, detail="unauthenticated")
    row = db.get(UserAccess, asurite)
    if not row or row.role != "admin":
        raise HTTPException(status_code=403, detail="forbidden")
    return asurite



def serialize_user_access(r: UserAccess) -> dict:
    base = {
        "asu_id": r.asu_id,
        "role": r.role,

        # flags your admin grid expects at top-level
        "assignment_adder": bool(r.assignment_adder),
        "applications": bool(r.applications),
        "phd_applications": bool(r.phd_applications),
        "student_summary_page": bool(r.student_summary_page),
        "bulk_upload_assignments": bool(r.bulk_upload_assignments),
        "manage_assignments": bool(r.manage_assignments),
        "login": bool(r.login),
        "master_dashboard": bool(r.master_dashboard),
        "faculty_dashboard": bool(r.faculty_dashboard),  # ← ADD THIS
    }

    # optional profile fields (handy in the grid)
    base["email"] = r.email
    base["emplid"] = r.emplid
    base["name"] = r.name
    base["position_title"] = r.position_title
    base["program"] = r.program

    # merged perms (if other parts of the app need it)
    row_dict = base.copy()
    base["perms"] = merged_perms(r.role, row_dict)

    return base


# def serialize_user_access(r: UserAccess) -> dict:
#     # Only include explicit columns (avoid _sa_instance_state)
#     base = {
#         "asu_id": r.asu_id,
#         "role": r.role,
#
#         # flags as stored in DB (booleans) — useful for your admin grid
#         "assignment_adder": r.assignment_adder,
#         "applications": r.applications,
#         "phd_applications": r.phd_applications,
#         "student_summary_page": r.student_summary_page,
#         "bulk_upload_assignments": r.bulk_upload_assignments,
#         "manage_assignments": r.manage_assignments,
#         "login": r.login,
#         "master_dashboard": r.master_dashboard,
#     }
#     # Build perms (booleans) using role defaults + overrides
#     row_dict = base.copy()
#     perms = merged_perms(r.role, row_dict)
#     base["perms"] = perms        # ✅ canonical perms object
#     return base

@router.get("/users")
def list_users(db: Session = Depends(get_db), me: str = Depends(require_admin)):
    rows = db.query(UserAccess).all()
    return [serialize_user_access(r) for r in rows]

@router.post("/users")
def create_user(payload: dict, db: Session = Depends(get_db), me: str = Depends(require_admin)):
    asu_id = payload["asu_id"].lower()
    role = payload["role"]
    if db.get(UserAccess, asu_id):
        raise HTTPException(status_code=400, detail="asu_id exists")

    # Start from role defaults; override with payload if provided
    role_defaults = ROLE_DEFAULTS.get(role, {})
    flags = {
        k: bool(payload.get(k, role_defaults.get(k, False)))
        for k in ROLE_DEFAULTS["admin"].keys()
    }

    r = UserAccess(asu_id=asu_id, role=role, **flags)
    db.add(r)
    db.commit()
    db.refresh(r)
    return serialize_user_access(r)

@router.patch("/users/{asu_id}")
def update_user(asu_id: str, payload: dict, db: Session = Depends(get_db), me: str = Depends(require_admin)):
    r = db.get(UserAccess, asu_id.lower())
    if not r:
        raise HTTPException(status_code=404, detail="not found")

    if "role" in payload:
        r.role = payload["role"]

    for k in ROLE_DEFAULTS["admin"].keys():
        if k in payload:
            setattr(r, k, bool(payload[k]))

    db.commit()
    db.refresh(r)
    return serialize_user_access(r)

@router.delete("/users/{asu_id}")
def delete_user(asu_id: str, db: Session = Depends(get_db), me: str = Depends(require_admin)):
    r = db.get(UserAccess, asu_id.lower())
    if not r:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(r)
    db.commit()
    return {"ok": True}

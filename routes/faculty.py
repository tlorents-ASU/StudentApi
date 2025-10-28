# # routes/faculty.py
# from fastapi import APIRouter, Depends, HTTPException
# from typing import List, Optional
# from pydantic import BaseModel
#
# from sqlalchemy.orm import Session
#
# # ↓ Update these imports to match your project structure
# from auth import current_user
# from database import get_db
# from models.assignment import StudentClassAssignment  # your SQLAlchemy ORM model
#
# router = APIRouter(prefix="/api/faculty", tags=["faculty"])
#
# # Safer, read-only subset for faculty
# class FacultyAssignmentRead(BaseModel):
#     Id: int
#     Student_ID: int
#     ASUrite: Optional[str] = None
#     Position: str
#     WeeklyHours: int
#     FultonFellow: str
#     Email: str
#     EducationLevel: str
#     Subject: str
#     CatalogNum: int
#     ClassSession: str
#     ClassNum: str
#     Term: str
#     InstructorFirstName: str
#     InstructorLastName: str
#     Location: str
#     Campus: str
#     AcadCareer: str
#     First_Name: Optional[str] = None
#     Last_Name: Optional[str] = None
#     cum_gpa: Optional[float] = None
#     cur_gpa: Optional[float] = None
#
#     class Config:
#         from_attributes = True
#
#
# def require_flag(user: dict, flag: str) -> None:
#     """
#     Minimal in-file guard. If you already have a helper in rbac.py,
#     feel free to import and use that instead.
#     """
#     if not user or not bool(user.get(flag)):
#         raise HTTPException(status_code=403, detail="Forbidden")
#
#
# @router.get("/student-assignments", response_model=List[FacultyAssignmentRead])
# def get_faculty_assignments(
#     db: Session = Depends(get_db),
#     user=Depends(get_user),
# ):
#     # Gate access
#     require_flag(user, "faculty_dashboard")
#
#     # Fetch all assignments. If you need term/course filters, add query params later.
#     rows = db.query(StudentClassAssignment).all()
#
#     # Return ONLY the fields defined in FacultyAssignmentRead.
#     # (Pydantic will ignore extra attributes, but we build a clean dict to be explicit
#     #  and to avoid any accidental leaks if models change.)
#     safe = []
#     for r in rows:
#         safe.append({
#             "Id": r.Id,
#             "Student_ID": r.Student_ID,
#             "ASUrite": r.ASUrite,
#             "Position": r.Position,
#             "WeeklyHours": r.WeeklyHours,
#             "FultonFellow": r.FultonFellow,
#             "Email": r.Email,
#             "EducationLevel": r.EducationLevel,
#             "Subject": r.Subject,
#             "CatalogNum": r.CatalogNum,
#             "ClassSession": r.ClassSession,
#             "ClassNum": r.ClassNum,
#             "Term": r.Term,
#             "InstructorFirstName": r.InstructorFirstName,
#             "InstructorLastName": r.InstructorLastName,
#             "Location": r.Location,
#             "Campus": r.Campus,
#             "AcadCareer": r.AcadCareer,
#             "First_Name": getattr(r, "First_Name", None),
#             "Last_Name": getattr(r, "Last_Name", None),
#             "cum_gpa": getattr(r, "cum_gpa", None),
#             "cur_gpa": getattr(r, "cur_gpa", None),
#         })
#     return safe



# routes/faculty.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from database import get_db
from models.assignment import StudentClassAssignment
from routes.auth import current_user  # <-- use the pure dependency

router = APIRouter(prefix="/api/faculty", tags=["faculty"])

class FacultyAssignmentRead(BaseModel):
    Id: int
    Student_ID: int
    ASUrite: Optional[str] = None
    Position: str
    WeeklyHours: int
    FultonFellow: str
    Email: str
    EducationLevel: str
    Subject: str
    CatalogNum: int
    ClassSession: str
    ClassNum: str
    Term: str
    InstructorFirstName: str
    InstructorLastName: str
    Location: str
    Campus: str
    AcadCareer: str
    First_Name: Optional[str] = None
    Last_Name: Optional[str] = None
    cum_gpa: Optional[float] = None
    cur_gpa: Optional[float] = None

    class Config:
        from_attributes = True

def require_perm(user: dict, flag: str) -> None:
    if not user or not user.get("perms", {}).get(flag, False):
        raise HTTPException(status_code=403, detail="Forbidden")

@router.get("/student-assignments", response_model=List[FacultyAssignmentRead])
def get_faculty_assignments(
    db: Session = Depends(get_db),
    user: dict = Depends(current_user),
):
    # Gate access
    require_perm(user, "faculty_dashboard")

    rows = db.query(StudentClassAssignment).filter(StudentClassAssignment.Instructor_Edit.is_(None)).all()

    safe = []
    for r in rows:
        safe.append({
            "Id": r.Id,
            "Student_ID": r.Student_ID,
            "ASUrite": r.ASUrite,
            "Position": r.Position,
            "WeeklyHours": r.WeeklyHours,
            "FultonFellow": r.FultonFellow,
            "Email": r.Email,
            "EducationLevel": r.EducationLevel,
            "Subject": r.Subject,
            "CatalogNum": r.CatalogNum,
            "ClassSession": r.ClassSession,
            "ClassNum": r.ClassNum,
            "Term": r.Term,
            "InstructorFirstName": r.InstructorFirstName,
            "InstructorLastName": r.InstructorLastName,
            "Location": r.Location,
            "Campus": r.Campus,
            "AcadCareer": r.AcadCareer,
            "First_Name": getattr(r, "First_Name", None),
            "Last_Name": getattr(r, "Last_Name", None),
            "cum_gpa": getattr(r, "cum_gpa", None),
            "cur_gpa": getattr(r, "cur_gpa", None),
        })
    return safe

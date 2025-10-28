from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import csv
import io
from fastapi.responses import StreamingResponse


from models.assignment import StudentClassAssignment
from models.class_schedule import ClassSchedule2261
from schemas.assignment_dto import StudentAssignmentUpdateDto
from database import get_db
from utils.assignment_utils import calculate_compensation, compute_cost_center_key, infer_acad_career
from schemas.assignment_schema import StudentClassAssignmentCreate
from schemas.assignment import StudentClassAssignmentRead
from models.student import StudentLookup
from fastapi.responses import JSONResponse
from sqlalchemy import or_



router = APIRouter(prefix="/api/StudentClassAssignment", tags=["StudentClassAssignment"])


# GET all
@router.get("/", response_model=List[StudentClassAssignmentRead])
def get_assignments(db: Session = Depends(get_db)):
    return db.query(StudentClassAssignment).filter(StudentClassAssignment.Instructor_Edit.is_(None)).all()


@router.get("/template")
def download_template():
    """Download the new simplified 5-header template"""
    headers = [
        "Position", "FultonFellow", "WeeklyHours", "Student_ID (ID number OR ASUrite accepted)", "ClassNum"
    ]
    csv_content = ",".join(headers) + "\n"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=BulkUploadTemplate.csv"}
    )


@router.get("/template-legacy")
def download_legacy_template():
    """Download the legacy 12-header template for faculty who prefer the old format"""
    headers = [
        "Position", "FultonFellow", "WeeklyHours", "Student_ID (ID number OR ASUrite accepted)", "First_Name",
        "Last_Name", "Email", "EducationLevel", "Subject", "CatalogNum",
        "ClassSession", "ClassNum"
    ]
    csv_content = ",".join(headers) + "\n"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=BulkUploadTemplate_Legacy.csv"}
    )


# GET by ID
@router.get("/{assignment_id}", response_model=dict)
def get_assignment(assignment_id: int, db: Session = Depends(get_db)):
    assignment = db.query(StudentClassAssignment).filter_by(Id=assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {
        "Id": assignment.Id,
        "Position_Number": assignment.Position_Number,
        "SSN_Sent": assignment.SSN_Sent,
        "Offer_Sent": assignment.Offer_Sent,
        "Offer_Signed": assignment.Offer_Signed,
    }


# --- Get total hours by student
@router.get("/totalhours/{student_id}", response_model=int)
def get_total_hours(student_id: int, db: Session = Depends(get_db)):
    total = db.query(StudentClassAssignment).filter(
        StudentClassAssignment.Student_ID == student_id,
        or_(
            StudentClassAssignment.Instructor_Edit == None,
            StudentClassAssignment.Instructor_Edit == '',
            StudentClassAssignment.Instructor_Edit == 'N'  # if you use this as a default for active
        )
    ).with_entities(
        StudentClassAssignment.WeeklyHours
    ).all()

    return sum([a[0] for a in total])


# POST single assignment
@router.post("/", status_code=201)
def create_assignment(assignment: StudentClassAssignmentCreate, db: Session = Depends(get_db)):
    new_assignment = StudentClassAssignment(**assignment.model_dump())
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)
    return {"message": "Assignment created", "id": new_assignment.Id}


# PUT update assignment
@router.put("/{assignment_id}", status_code=204)
def update_assignment(assignment_id: int, update_data: StudentAssignmentUpdateDto, db: Session = Depends(get_db)):
    assignment = db.query(StudentClassAssignment).filter_by(Id=assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(assignment, field, value)

    db.commit()
    return


# Post Bulk Upload - Supports both 5-header and 17-header templates
@router.post("/upload")
def upload_assignments(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=400, detail="CSV or XLSX required.")
    try:
        # Read CSV (Excel not handled in this backend example, but could be added)
        content = file.file.read().decode("utf-8-sig")
        csv_reader = csv.DictReader(io.StringIO(content))

        # Detect which template format is being used by checking headers
        fieldnames = csv_reader.fieldnames or []
        is_legacy_format = "First_Name" in fieldnames and "Last_Name" in fieldnames and "Email" in fieldnames

    except Exception as e:
        raise HTTPException(status_code=400, detail="Could not read CSV: " + str(e))

    records = []
    now = datetime.now(timezone.utc)

    if is_legacy_format:
        # --- LEGACY 12-HEADER FORMAT ---
        required_fields = [
            "Position", "WeeklyHours", "Student_ID (ID number OR ASUrite accepted)", "ClassNum",
            "First_Name", "Last_Name", "Email", "EducationLevel", "Subject", "CatalogNum", "ClassSession"
        ]

        for idx, row in enumerate(csv_reader, start=2):
            # Validate required fields
            for field in required_fields:
                if field not in row or not str(row[field]).strip():
                    raise HTTPException(422, f"Missing field '{field}' in row {idx} (Legacy format)")

            # Set FultonFellow to 'No' if blank
            fulton = str(row.get("FultonFellow", "")).strip()
            fulton_fellow = fulton if fulton else "No"

            # Student lookup (for validation and to get GPA data)
            student_id_or_asurite = row["Student_ID (ID number OR ASUrite accepted)"].strip()
            student = None
            if student_id_or_asurite.isdigit():
                student = db.query(StudentLookup).filter(StudentLookup.Student_ID == int(student_id_or_asurite)).first()
            else:
                student = db.query(StudentLookup).filter(StudentLookup.ASUrite.ilike(student_id_or_asurite)).first()
            if not student:
                raise HTTPException(422, f"Student '{student_id_or_asurite}' not found (row {idx})")

            # Class lookup (for validation and to get Term/AcadCareer/Instructor/Location/Campus from DB)
            class_num = row["ClassNum"].strip()
            class_obj = db.query(ClassSchedule2261).filter_by(ClassNum=class_num).first()
            if not class_obj:
                raise HTTPException(422, f"ClassNum '{class_num}' not found (row {idx})")

            # Calculate compensation and cost center using PROVIDED values from CSV + DB lookups
            weekly_hours = int(row["WeeklyHours"])
            position = row["Position"]
            education_level = row["EducationLevel"].strip()
            session = row["ClassSession"].strip()

            compensation = calculate_compensation({
                "WeeklyHours": weekly_hours,
                "Position": position,
                "EducationLevel": education_level,
                "FultonFellow": fulton_fellow,
                "ClassSession": session
            })
            cost_center = compute_cost_center_key({
                "Position": position,
                "Location": class_obj.Location,  # From DB
                "Campus": class_obj.Campus,  # From DB
                "AcadCareer": class_obj.AcadCareer  # From DB
            })

            # Create assignment using PROVIDED values from CSV + DB lookups
            assignment = StudentClassAssignment(
                Student_ID=student.Student_ID,
                ASUrite=student.ASUrite,
                Position=position,
                FultonFellow=fulton_fellow,
                WeeklyHours=weekly_hours,
                Email=row["Email"].strip(),
                First_Name=row["First_Name"].strip(),
                Last_Name=row["Last_Name"].strip(),
                EducationLevel=education_level,
                Subject=row["Subject"].strip(),
                CatalogNum=row["CatalogNum"].strip(),
                ClassSession=session,
                ClassNum=class_num,
                Term=class_obj.Term,  # From DB
                InstructorFirstName=class_obj.InstructorFirstName,  # From DB
                InstructorLastName=class_obj.InstructorLastName,  # From DB
                InstructorID=class_obj.InstructorID,  # From DB
                Location=class_obj.Location,  # From DB
                Campus=class_obj.Campus,  # From DB
                AcadCareer=class_obj.AcadCareer,  # From DB
                CostCenterKey=cost_center,
                Compensation=compensation,
                CreatedAt=now,
                cum_gpa=float(student.Cumulative_GPA or 0),
                cur_gpa=float(student.Current_GPA or 0),
            )
            records.append(assignment)
    else:
        # --- NEW 5-HEADER FORMAT (AUTO-COMPLETE) ---
        required_fields = ["Position", "WeeklyHours", "Student_ID (ID number OR ASUrite accepted)", "ClassNum"]

        for idx, row in enumerate(csv_reader, start=2):
            # --- Validate required fields (except FultonFellow, which is optional) ---
            for field in required_fields:
                if field not in row or not str(row[field]).strip():
                    raise HTTPException(422, f"Missing field '{field}' in row {idx}")

            # --- Set FultonFellow to 'No' if it's blank or empty or missing ---
            fulton = str(row.get("FultonFellow", "")).strip()
            row["FultonFellow"] = fulton if fulton else "No"

            # --- Student Lookup ---
            student_id_or_asurite = row["Student_ID (ID number OR ASUrite accepted)"].strip()
            student = None
            if student_id_or_asurite.isdigit():
                student = db.query(StudentLookup).filter(StudentLookup.Student_ID == int(student_id_or_asurite)).first()
            else:
                student = db.query(StudentLookup).filter(StudentLookup.ASUrite.ilike(student_id_or_asurite)).first()
            if not student:
                raise HTTPException(422, f"Student '{student_id_or_asurite}' not found (row {idx})")

            # --- Class Lookup ---
            class_num = row["ClassNum"].strip()
            class_obj = db.query(ClassSchedule2261).filter_by(ClassNum=class_num).first()
            if not class_obj:
                raise HTTPException(422, f"ClassNum '{class_num}' not found (row {idx})")

            # --- Compose calculated fields ---
            weekly_hours = int(row["WeeklyHours"])
            position = row["Position"]
            fulton_fellow = row["FultonFellow"]
            session = class_obj.Session

            compensation = calculate_compensation({
                "WeeklyHours": weekly_hours,
                "Position": position,
                "EducationLevel": student.Degree,
                "FultonFellow": fulton_fellow,
                "ClassSession": session
            })
            cost_center = compute_cost_center_key({
                "Position": position,
                "Location": class_obj.Location,
                "Campus": class_obj.Campus,
                "AcadCareer": class_obj.AcadCareer
            })

            # --- Compose assignment object ---
            assignment = StudentClassAssignment(
                Student_ID=student.Student_ID,
                ASUrite=student.ASUrite,
                Position=position,
                FultonFellow=fulton_fellow,
                WeeklyHours=weekly_hours,
                Email=student.ASU_Email_Adress,
                First_Name=student.First_Name,
                Last_Name=student.Last_Name,
                EducationLevel=student.Degree,
                Subject=class_obj.Subject,
                CatalogNum=class_obj.CatalogNum,
                ClassSession=class_obj.Session,
                ClassNum=class_num,
                Term=class_obj.Term,
                InstructorFirstName=class_obj.InstructorFirstName,
                InstructorLastName=class_obj.InstructorLastName,
                InstructorID=class_obj.InstructorID,
                Location=class_obj.Location,
                Campus=class_obj.Campus,
                AcadCareer=class_obj.AcadCareer,
                CostCenterKey=cost_center,
                Compensation=compensation,
                CreatedAt=now,
                cum_gpa=float(student.Cumulative_GPA or 0),
                cur_gpa=float(student.Current_GPA or 0),
            )
            records.append(assignment)

    db.bulk_save_objects(records)
    db.commit()

    format_type = "legacy 12-header" if is_legacy_format else "new 5-header"
    return {"message": f"{len(records)} assignments uploaded successfully using {format_type} format."}


# NEW: Get assignment summary for a student (by Student_ID or ASUrite)
@router.get("/student-summary/{identifier}")
def get_assignment_summary(identifier: str, db: Session = Depends(get_db)):
    # Lookup student by Student_ID or ASUrite
    if identifier.isdigit():
        student = db.query(StudentLookup).filter(StudentLookup.Student_ID == int(identifier)).first()
    else:
        student = db.query(StudentLookup).filter(StudentLookup.ASUrite.ilike(identifier)).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get all assignments for this student
    assignments = db.query(StudentClassAssignment).filter(
        StudentClassAssignment.Student_ID == student.Student_ID,
        StudentClassAssignment.Instructor_Edit.is_(None)
    ).all()

    # Tally hours by session
    session_hours = {"A": 0, "B": 0, "C": 0}
    assignment_list = []
    for a in assignments:
        session = (a.ClassSession or "").strip().upper()
        if session in session_hours:
            session_hours[session] += a.WeeklyHours
        assignment_list.append({
            "Id": a.Id,
            "Position": a.Position,
            "WeeklyHours": a.WeeklyHours,
            "ClassSession": a.ClassSession,
            "Subject": a.Subject,
            "CatalogNum": a.CatalogNum,
            "ClassNum": a.ClassNum,
            "InstructorName": f"{a.InstructorFirstName} {a.InstructorLastName}",
            "AcadCareer": a.AcadCareer,
        })

    # Compose response
    return {
        "StudentName": f"{student.First_Name or ''} {student.Last_Name or ''}".strip(),
        "ASUrite": student.ASUrite,
        "Student_ID": student.Student_ID,
        "Position": assignments[0].Position if assignments else None,
        "FultonFellow": assignments[0].FultonFellow if assignments else None,
        "EducationLevel": assignments[0].EducationLevel if assignments else None,
        "sessionA": session_hours["A"],
        "sessionB": session_hours["B"],
        "sessionC": session_hours["C"],
        "assignments": assignment_list
    }



def get_changed_fields(new_assign, orig, editable_fields):
    changed = []
    for field in editable_fields:
        # The actual attribute names must match your ORM model
        if getattr(new_assign, field) != getattr(orig, field):
            changed.append(field)
    return changed

@router.post("/bulk-edit")
def bulk_edit_assignments(
    updates: dict,
    db: Session = Depends(get_db)
):
    """
    Request body format:
    {
        "updates": [{ "id": 123, "Position": ..., "WeeklyHours": ..., "ClassNum": ...}, ...],
        "deletes": [456, 789],
        "studentId": "ASUrite or Student_ID"
    }
    Returns:
    {
        "updated": [{...assignment fields..., "changed_fields": [...]}, ...],
        "deleted": [456, ...]
    }
    """
    student_id = updates.get("studentId")
    update_rows = updates.get("updates", [])
    delete_ids = updates.get("deletes", [])

    # Find student
    if not student_id:
        raise HTTPException(400, "No studentId provided")
    if str(student_id).isdigit():
        student = db.query(StudentLookup).filter(StudentLookup.Student_ID == int(student_id)).first()
    else:
        student = db.query(StudentLookup).filter(StudentLookup.ASUrite.ilike(student_id)).first()
    if not student:
        raise HTTPException(404, "Student not found")

    updated_response = []
    editable_fields = ["Position", "WeeklyHours", "ClassNum"]  # List your editable fields

    # 1. Handle updates/edits
    for edit in update_rows:
        orig_id = edit["id"]
        orig = db.query(StudentClassAssignment).filter_by(Id=orig_id).first()
        if not orig:
            continue
        # Mark original as edited
        orig.Instructor_Edit = "Y"
        db.add(orig)
        db.flush()

        class_obj = None
        if "ClassNum" in edit and edit["ClassNum"] != orig.ClassNum:
            class_obj = db.query(ClassSchedule2261).filter_by(ClassNum=edit["ClassNum"], Term=orig.Term).first()
            if not class_obj:
                raise HTTPException(404, f"ClassNum {edit['ClassNum']} not found")

        # Always recalculate compensation & cost center based on new info
        comp = calculate_compensation({
            "WeeklyHours": edit["WeeklyHours"],
            "Position": edit["Position"],
            "EducationLevel": orig.EducationLevel,
            "FultonFellow": orig.FultonFellow,
            "ClassSession": class_obj.Session if class_obj else orig.ClassSession
        })
        cost_center = compute_cost_center_key({
            "Position": edit["Position"],
            "Location": class_obj.Location if class_obj else orig.Location,
            "Campus": class_obj.Campus if class_obj else orig.Campus,
            "AcadCareer": class_obj.AcadCareer if class_obj else orig.AcadCareer
        })

        # New assignment
        new_assign = StudentClassAssignment(
            Student_ID=orig.Student_ID,
            ASUrite=orig.ASUrite,
            Position=edit["Position"],
            WeeklyHours=edit["WeeklyHours"],
            FultonFellow=orig.FultonFellow,
            Email=orig.Email,
            EducationLevel=orig.EducationLevel,
            Subject=class_obj.Subject if class_obj else orig.Subject,
            CatalogNum=class_obj.CatalogNum if class_obj else orig.CatalogNum,
            ClassSession=class_obj.Session if class_obj else orig.ClassSession,
            ClassNum=edit["ClassNum"] if "ClassNum" in edit else orig.ClassNum,
            Term=orig.Term,
            InstructorFirstName=class_obj.InstructorFirstName if class_obj else orig.InstructorFirstName,
            InstructorLastName=class_obj.InstructorLastName if class_obj else orig.InstructorLastName,
            InstructorID=class_obj.InstructorID if class_obj else orig.InstructorID,
            Compensation=comp,
            Location=class_obj.Location if class_obj else orig.Location,
            Campus=class_obj.Campus if class_obj else orig.Campus,
            AcadCareer=class_obj.AcadCareer if class_obj else orig.AcadCareer,
            CostCenterKey=cost_center,
            cur_gpa=orig.cur_gpa,
            cum_gpa=orig.cum_gpa,
            CreatedAt=datetime.now(timezone.utc),
            Instructor_Edit=None,  # Not edited yet
            First_Name=orig.First_Name,
            Last_Name=orig.Last_Name,
            Position_Number=orig.Position_Number,
            SSN_Sent=orig.SSN_Sent,
            Offer_Sent=orig.Offer_Sent,
            Offer_Signed=orig.Offer_Signed
        )
        db.add(new_assign)
        db.flush()  # Get new_assign.Id if autoincrement

        # Find changed fields for highlighting
        changed_fields = get_changed_fields(new_assign, orig, editable_fields)

        # Prepare row for response (add other fields if needed)
        row_dict = {col.name: getattr(new_assign, col.name) for col in StudentClassAssignment.__table__.columns}
        row_dict['changed_fields'] = changed_fields
        updated_response.append(row_dict)

    # 2. Handle deletions
    for del_id in delete_ids:
        orig = db.query(StudentClassAssignment).filter_by(Id=del_id).first()
        if orig:
            orig.Instructor_Edit = "D"
            db.add(orig)
    db.commit()
    return {
        "updated": updated_response,
        "deleted": delete_ids,
        "status": "success"
    }



# NEW Test feature to calibrate a preview of the 5 headers before saving to DB (TESTING)
@router.post("/calibrate-preview")
async def calibrate_preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Accepts a CSV with headers:
    'Position', 'FultonFellow', 'WeeklyHours', 'Student_ID (ID number OR ASUrite accepted)', 'ClassNum'
    Returns a preview list combining info from StudentLookup and ClassSchedule2261 for each row.
    """
    # Parse uploaded file
    try:
        content = await file.read()
        decoded = content.decode("utf-8-sig")
        csv_reader = csv.DictReader(io.StringIO(decoded))
    except Exception as e:
        raise HTTPException(400, f"Failed to read CSV: {e}")

    required_fields = ["Position", "WeeklyHours", "Student_ID (ID number OR ASUrite accepted)", "ClassNum"]
    preview_data = []

    for idx, row in enumerate(csv_reader, start=2):
        # --- Validate required fields ---
        for field in required_fields:
            if field not in row or not str(row[field]).strip():
                raise HTTPException(422, f"Missing field '{field}' in row {idx}")

        # --- Default FultonFellow to "No" if missing/blank ---
        fulton = str(row.get("FultonFellow", "")).strip()
        row["FultonFellow"] = fulton if fulton else "No"

        # --- Student lookup ---
        sid = row["Student_ID (ID number OR ASUrite accepted)"].strip()
        student = None
        if sid.isdigit():
            student = db.query(StudentLookup).filter_by(Student_ID=int(sid)).first()
        else:
            student = db.query(StudentLookup).filter(StudentLookup.ASUrite.ilike(sid)).first()
        if not student:
            raise HTTPException(422, f"Student not found for '{sid}' (row {idx})")

        # --- Class lookup ---
        classnum = row["ClassNum"].strip()
        class_obj = db.query(ClassSchedule2261).filter_by(ClassNum=classnum).first()
        if not class_obj:
            raise HTTPException(422, f"ClassNum not found: '{classnum}' (row {idx})")

        # --- Compose the preview object (all fields, including new) ---
        preview_row = {
            # Uploaded fields
            "Position": row["Position"],
            "FultonFellow": row["FultonFellow"],
            "WeeklyHours": row["WeeklyHours"],
            "Student_ID": student.Student_ID,
            "ASUrite": student.ASUrite,
            "ClassNum": class_obj.ClassNum,

            # Student Info
            "First_Name": student.First_Name,
            "Last_Name": student.Last_Name,
            "ASU_Email_Adress": student.ASU_Email_Adress,
            "Degree": student.Degree,
            "cum_gpa": float(student.Cumulative_GPA or 0),
            "cur_gpa": float(student.Current_GPA or 0),

            # Class Info (including new columns)
            "Subject": class_obj.Subject,
            "CatalogNum": class_obj.CatalogNum,
            "SectionNum": class_obj.SectionNum,
            "Title": class_obj.Title,
            "Term": class_obj.Term,
            "Session": class_obj.Session,
            "InstructorID": class_obj.InstructorID,
            "InstructorFirstName": class_obj.InstructorFirstName,
            "InstructorLastName": class_obj.InstructorLastName,
            "InstructorEmail": class_obj.InstructorEmail,
            "Location": class_obj.Location,
            "Campus": class_obj.Campus,
            "AcadCareer": class_obj.AcadCareer,
            # --- New Class Fields ---
            # "CombineSectionID": class_obj.CombineSectionID,
            "Component": class_obj.Component,
            "EndDate": class_obj.EndDate.isoformat() if class_obj.EndDate else None,
            "EnrollCap": class_obj.EnrollCap,
            "EnrollTotal": class_obj.EnrollTotal,
            "InstructMode": class_obj.InstructMode,
        }
        preview_data.append(preview_row)

    return JSONResponse(content=preview_data)
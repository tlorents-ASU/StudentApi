from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models.phd_application import PhdApplication
from schemas.phd_application_summary import PhdApplicationSummaryDto

router = APIRouter(prefix="/api/PhdApplication", tags=["PhdApplication"])


@router.get("", response_model=List[PhdApplicationSummaryDto])
@router.get("/", response_model=List[PhdApplicationSummaryDto])
def get_phd_application_summaries(db: Session = Depends(get_db)):
    applications = db.query(PhdApplication).all()
    return [
        PhdApplicationSummaryDto(
            Id=app.Id,
            Email=app.Email,
            Name=app.Name,
            YourASUEmailAddress=app.YourASUEmailAddress,
            FirstName=app.FirstName,
            LastName=app.LastName,
            ASU10DigitID=app.ASU10DigitID,
            DegreeProgram=app.DegreeProgram,
            ExpectedGraduation=app.ExpectedGraduation,
            GraduateGPA=app.GraduateGPA,
            PositionsConsidered=app.PositionsConsidered,
            PreferredCourses=app.PreferredCourses,
            TranscriptUrl=app.TranscriptUrl,
            ResumeUrl=app.ResumeUrl,
            HoursAvailable=app.HoursAvailable,
            ProgrammingLanguages=app.ProgrammingLanguages,  # <-- plural to match schema
            TASpeakTestScoreOrIBT=app.TASpeakTestScoreOrIBT,
            DissertationProposalStatus=app.DissertationProposalStatus,
            ComprehensiveExam=app.ComprehensiveExam,  # <-- include
            ResearchAccomplishments=app.ResearchAccomplishments,  # <-- include
            UndergraduateInstitution=app.UndergraduateInstitution,
            UndergraduateGPA=app.UndergraduateGPA,
            StartOfPhdYear=app.StartOfPhdYear
        )
        for app in applications
    ]

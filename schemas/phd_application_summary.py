from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

class PhdApplicationSummaryDto(BaseModel):
    Id: int
    Email: str
    Name: str
    YourASUEmailAddress: str
    FirstName: str
    LastName: str
    ASU10DigitID: int
    DegreeProgram: str
    ExpectedGraduation: date
    GraduateGPA: Optional[str]
    PositionsConsidered: Optional[str]
    PreferredCourses: Optional[str]
    TranscriptUrl: Optional[str]
    ResumeUrl: Optional[str]
    HoursAvailable: Optional[str]
    ProgrammingLanguages: str
    TASpeakTestScoreOrIBT: Optional[str]
    DissertationProposalStatus: Optional[str]
    ComprehensiveExam: Optional[str]
    ResearchAccomplishments: Optional[str]
    UndergraduateInstitution: str
    UndergraduateGPA: str
    StartOfPhdYear: str

    class Config:
        orm_mode = True
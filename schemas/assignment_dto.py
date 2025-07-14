from pydantic import BaseModel
from typing import Optional


class StudentAssignmentUpdateDto(BaseModel):
    Position_Number: Optional[str] = None
    SSN_Sent: Optional[bool]
    Offer_Sent: Optional[bool]
    Offer_Signed: Optional[bool]

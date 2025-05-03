from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    email: str  # Changed from EmailStr to str
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    is_admin: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class QuestionBase(BaseModel):
    question_text: str
    answer: str
    marks: int

class QuestionCreate(QuestionBase):
    pass

class Question(QuestionBase):
    id: int
    paper_id: int

    class Config:
        from_attributes = True  # Changed from orm_mode = True

class PaperBase(BaseModel):
    title: str
    description: str
    duration_minutes: int
    total_marks: int

class PaperCreate(PaperBase):
    pass

class PaperUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    # Add any other fields that should be updatable
    duration_minutes: Optional[int] = None
    total_marks: Optional[int] = None

class Paper(PaperBase):
    id: int
    pdf_path: Optional[str] = None
    questions: List[Question] = []

    class Config:
        from_attributes = True  # Changed from orm_mode = True

class SubmissionBase(BaseModel):
    paper_id: int
    score: int
    completed_at: str

class SubmissionCreate(SubmissionBase):
    pass

class Submission(SubmissionBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True  # Changed from orm_mode = True

class PaperUploadResponse(BaseModel):
    paper_id: int
    title: str
    pdf_path: str


class PaperSubmissionBase(BaseModel):
    time_spent: int
    marks: int

class PaperSubmissionCreate(PaperSubmissionBase):
    pass

class PaperSubmission(PaperSubmissionBase):
    id: int
    paper_id: int
    user_id: int
    submitted_at: datetime

    class Config:
        orm_mode = True
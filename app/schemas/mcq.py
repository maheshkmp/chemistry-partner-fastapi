from pydantic import BaseModel
from typing import List

class MCQAnswerCreate(BaseModel):
    question_number: int
    correct_option: int

class MCQAnswer(MCQAnswerCreate):
    id: int
    paper_id: int

    class Config:
        orm_mode = True

class PaperSubmission(BaseModel):
    answers: List[dict]
    time_spent: int

class AnswerSubmission(BaseModel):
    question_number: int
    selected_option: int

class UserAnswerSubmit(BaseModel):
    answers: List[AnswerSubmission]
    time_spent: int

class SubmissionResult(BaseModel):
    total_correct: int
    total_questions: int = 50
    score_percentage: float
    time_spent: int
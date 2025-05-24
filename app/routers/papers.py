@router.put("/{paper_id}")
async def update_paper(
    paper_id: int,
    title: str = Form(...),
    description: str = Form(...),
    duration_minutes: int = Form(...),
    total_marks: int = Form(...),
    pdf_file: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Update paper details
    paper.title = title
    paper.description = description
    paper.duration_minutes = duration_minutes
    paper.total_marks = total_marks
    
    # Handle PDF file update if provided
    if pdf_file:
        # Save the new PDF file
        file_path = f"papers/{paper_id}_{pdf_file.filename}"
        with open(file_path, "wb") as f:
            content = await pdf_file.read()
            f.write(content)
        paper.pdf_file_path = file_path
    
    db.commit()
    return {"message": "Paper updated successfully"}


from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
import pandas as pd
from io import BytesIO
from typing import List
from ..models import MCQAnswer, Paper, User, Submission
from ..schemas.mcq import MCQAnswerCreate, PaperSubmission, SubmissionResult
from ..database import get_db
from ..auth import get_current_user, get_current_admin_user

router = APIRouter()

@router.get("/{paper_id}")
async def get_paper(paper_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper

@router.post("/{paper_id}/answers/upload")
async def upload_answers_excel(
    paper_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files are allowed")

    try:
        # Read Excel file
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
        
        # Validate Excel structure
        required_columns = ['question_number', 'correct_option']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(status_code=400, detail="Invalid Excel format")

        # Clear existing answers
        db.query(MCQAnswer).filter(MCQAnswer.paper_id == paper_id).delete()

        # Add new answers
        for _, row in df.iterrows():
            answer = MCQAnswer(
                paper_id=paper_id,
                question_number=int(row['question_number']),
                correct_option=int(row['correct_option'])
            )
            db.add(answer)

        db.commit()
        return {"message": "Answers uploaded successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{paper_id}/results")
async def get_paper_results(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    # Get all submissions for this paper
    submissions = db.query(Submission).filter(Submission.paper_id == paper_id).all()
    
    # Get correct answers
    correct_answers = db.query(MCQAnswer).filter(MCQAnswer.paper_id == paper_id).all()
    correct_dict = {ans.question_number: ans.correct_option for ans in correct_answers}

    results = []
    for submission in submissions:
        student = db.query(User).filter(User.id == submission.user_id).first()
        
        # Calculate score
        total_correct = 0
        for answer in submission.answers:
            if (answer['question_number'] in correct_dict and 
                correct_dict[answer['question_number']] == answer['selected_option']):
                total_correct += 1

        results.append({
            "student_name": student.username,
            "total_correct": total_correct,
            "score_percentage": (total_correct / 50) * 100,
            "time_spent": submission.time_spent
        })

    return results

@router.post("/{paper_id}/submit")
async def submit_paper(
    paper_id: int,
    submission: PaperSubmission,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Get correct answers
    correct_answers = db.query(MCQAnswer).filter(MCQAnswer.paper_id == paper_id).all()
    if not correct_answers:
        raise HTTPException(status_code=404, detail="No answers found for this paper")

    correct_dict = {ans.question_number: ans.correct_option for ans in correct_answers}
    
    # Calculate score
    total_correct = 0
    for answer in submission.answers:
        if (answer.question_number in correct_dict and 
            correct_dict[answer.question_number] == answer.selected_option):
            total_correct += 1
    
    score_percentage = (total_correct / 50) * 100
    
    return SubmissionResult(
        total_correct=total_correct,
        score_percentage=score_percentage,
        time_spent=submission.time_spent
    )
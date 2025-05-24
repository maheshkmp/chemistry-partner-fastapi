# Standard library imports
import os
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import List

# Third-party imports
import bcrypt
import jwt
import pandas as pd
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    Request
)
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

# Local imports
from database import create_tables, get_db, engine
import models
import schemas

# Single instance of FastAPI
app = FastAPI()

# Update CORS middleware with proper configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chemistry-partner-react-maheshs-projects-9308879e.vercel.app",  # Remove trailing slash
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Update SECRET_KEY for production
SECRET_KEY = os.getenv("SECRET_KEY", "123")  # Make sure to set this in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
# Update the pwd_context configuration
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)

# Update the password hashing function
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Single instance of PDF directory
# Define upload directory
UPLOAD_DIR = Path("uploads/pdfs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Create tables once
create_tables()

# Keep all your helper functions together
# Remove duplicate function definitions
# Remove the second definition of:
# - verify_password
# - get_password_hash
# - datetime import

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Keep authentication functions together
# Update the jwt import
from jwt.exceptions import PyJWTError

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except PyJWTError:  # Changed from JWTError to PyJWTError
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: schemas.User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Keep all your endpoints together
@app.post("/papers/{paper_id}/upload-pdf", response_model=schemas.PaperUploadResponse)
async def upload_pdf(
    paper_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    # Verify admin access
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upload papers"
        )
    
    # Check if paper exists
    paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found"
        )
    
    # Validate file is PDF
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF document"
        )
    
    # Validate file size (e.g., 10MB max)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    file.file.seek(0, 2)  # Move to end of file
    file_size = file.file.tell()
    file.file.seek(0)  # Reset file pointer
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 10MB limit"
        )
    
    # Create unique filename with paper_id to avoid conflicts
    filename = f"paper_{paper_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    file_path = UPLOAD_DIR / filename
    
    # Save the uploaded file
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Update paper with pdf_path
    paper.pdf_path = str(file_path)
    db.commit()
    db.refresh(paper)
    
    return {
        "paper_id": paper.id,
        "title": paper.title,
        "pdf_path": paper.pdf_path
    }

limiter = Limiter(key_func=get_remote_address)



@app.post("/register", response_model=schemas.User)
async def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    try:
        db_user = db.query(models.User).filter(models.User.email == user.email).first()
        if db_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        hashed_password = get_password_hash(user.password)
        db_user = models.User(
            email=user.email,
            username=user.username,
            hashed_password=hashed_password,
            is_active=True,  # Add this line
            is_admin=False
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        print(f"Registration error: {str(e)}")  # This will log the error
        raise

@app.post("/token", response_model=schemas.Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "is_admin": user.is_admin,
        "username": user.username
    }


@app.post("/papers/", response_model=schemas.Paper)
async def create_paper(
    title: str = Form(...),
    description: str = Form(...),
    duration_minutes: int = Form(...),
    total_marks: int = Form(...),
    pdf_file: UploadFile = File(None),
    mcq_file: UploadFile = File(None),  # Add MCQ file upload
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    # Move validate_pdf_file logic inside create_paper
    async def validate_pdf_file(file: UploadFile) -> bool:
        if not file.filename.lower().endswith('.pdf'):
            return False
        content = await file.read(5)
        await file.seek(0)
        return content.startswith(b'%PDF-')

    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create papers"
        )
    
    # Create paper in database
    paper_data = {
        "title": title,
        "description": description,
        "duration_minutes": duration_minutes,
        "total_marks": total_marks
    }
    db_paper = models.Paper(**paper_data)
    db.add(db_paper)
    db.commit()
    db.refresh(db_paper)

    # Handle PDF upload if provided
    if pdf_file:
        if not await validate_pdf_file(pdf_file):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file format"
            )
        
        try:
            filename = f"paper_{db_paper.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            file_path = UPLOAD_DIR / filename
            
            with file_path.open("wb") as buffer:
                content = await pdf_file.read()
                buffer.write(content)
            
            db_paper.pdf_path = str(file_path)
            db.commit()
            db.refresh(db_paper)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save PDF file"
            )

    # Handle MCQ answer sheet upload if provided
    if mcq_file:
        if not mcq_file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="Only Excel files are allowed for MCQ answers"
            )

        try:
            # Read Excel file
            contents = await mcq_file.read()
            df = pd.read_excel(BytesIO(contents))
            
            # Validate Excel structure
            required_columns = ['question_number', 'correct_option']
            if not all(col in df.columns for col in required_columns):
                raise HTTPException(
                    status_code=400,
                    detail="Excel must contain 'question_number' and 'correct_option' columns"
                )

            # Add MCQ answers
            for _, row in df.iterrows():
                answer = models.MCQAnswer(
                    paper_id=db_paper.id,
                    question_number=int(row['question_number']),
                    correct_option=int(row['correct_option'])
                )
                db.add(answer)

            db.commit()

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing MCQ file: {str(e)}")
    
    return db_paper

@app.post("/papers/{paper_id}/submit", response_model=schemas.PaperSubmission)
async def submit_paper(
    paper_id: int,
    submission: schemas.PaperSubmissionCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    paper_submission = models.PaperSubmission(
        paper_id=paper_id,
        user_id=current_user.id,
        time_spent=submission.time_spent,
        marks=submission.marks,
        submitted_at=datetime.utcnow()
    )
    
    db.add(paper_submission)
    db.commit()
    db.refresh(paper_submission)
    return paper_submission


@app.get("/papers/{paper_id}/pdf")
@limiter.limit("5/minute")  # 5 requests per minute
async def get_pdf(
    request: Request,
    paper_id: int,
    token: str,
    db: Session = Depends(get_db)
):
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        
        # Get user
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid user")
        
        # Get paper
        paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        if not paper.pdf_path:
            raise HTTPException(status_code=404, detail="PDF not found for this paper")
        
        pdf_path = Path(paper.pdf_path)
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found on server")
        
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"paper_{paper_id}.pdf"
        )
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/papers/", response_model=List[schemas.Paper])
async def get_papers(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    try:
        papers = db.query(models.Paper).all()
        return papers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch papers"
        )

@app.get("/users/me", response_model=schemas.User)
async def get_current_user_info(current_user: schemas.User = Depends(get_current_active_user)):
    return current_user

@app.get("/users/{username}", response_model=schemas.User)
async def get_user_by_username(
    username: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/papers/submissions/user", response_model=List[schemas.PaperSubmission])
async def get_user_submissions(
    current_user: schemas.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    submissions = db.query(models.PaperSubmission)\
        .filter(models.PaperSubmission.user_id == current_user.id)\
        .order_by(models.PaperSubmission.submitted_at)\
        .all()
    return submissions

@app.put("/papers/{paper_id}", response_model=schemas.Paper)
async def update_paper(
    paper_id: int,
    title: str = Form(...),
    description: str = Form(...),
    duration_minutes: int = Form(...),
    total_marks: int = Form(...),
    pdf_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update papers"
        )
    
    paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Update paper details
    paper.title = title
    paper.description = description
    paper.duration_minutes = duration_minutes
    paper.total_marks = total_marks

    # Handle PDF upload if provided
    if pdf_file:
        # Delete old PDF if exists
        if paper.pdf_path:
            old_path = Path(paper.pdf_path)
            if old_path.exists():
                old_path.unlink()
        
        # Save new PDF
        filename = f"paper_{paper_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        file_path = UPLOAD_DIR / filename
        
        with file_path.open("wb") as buffer:
            content = await pdf_file.read()
            buffer.write(content)
        
        paper.pdf_path = str(file_path)
    
    db.commit()
    db.refresh(paper)
    return paper


@app.put("/users/{user_id}/admin", response_model=schemas.User)
async def set_admin_status(
    user_id: int,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_admin = True
    db.commit()
    db.refresh(user)
    return user



@app.delete("/papers/{paper_id}")
async def delete_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete papers"
        )
    
    paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # Delete associated PDF file if it exists
    if paper.pdf_path:
        pdf_path = Path(paper.pdf_path)
        if pdf_path.exists():
            pdf_path.unlink()
    
    # Delete paper from database
    db.delete(paper)
    db.commit()
    
    return {"message": "Paper deleted successfully"}


@app.get("/users/", response_model=List[schemas.User])
async def get_all_users(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view all users"
        )
    return db.query(models.User).all()

@app.get("/papers/submissions/all", response_model=List[schemas.PaperSubmission])
async def get_all_submissions(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view all submissions"
        )
    return db.query(models.PaperSubmission).all()


@app.post("/papers/{paper_id}/answers/upload")
async def upload_mcq_answers(
    paper_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upload answers"
        )

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Only Excel files are allowed"
        )

    try:
        # Read Excel file
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
        
        # Validate Excel structure
        required_columns = ['question_number', 'correct_option']
        if not all(col in df.columns for col in required_columns):
            raise HTTPException(
                status_code=400,
                detail="Excel must contain 'question_number' and 'correct_option' columns"
            )

        # Clear existing answers
        db.query(models.MCQAnswer).filter(models.MCQAnswer.paper_id == paper_id).delete()

        # Add new answers
        for _, row in df.iterrows():
            answer = models.MCQAnswer(
                paper_id=paper_id,
                question_number=int(row['question_number']),
                correct_option=int(row['correct_option'])
            )
            db.add(answer)

        db.commit()
        return {"message": "MCQ answers uploaded successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/papers/{paper_id}/answers/check")
async def check_user_answers(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    # Get the user's submission
    submission = db.query(models.PaperSubmission)\
        .filter(models.PaperSubmission.paper_id == paper_id)\
        .filter(models.PaperSubmission.user_id == current_user.id)\
        .first()
    
    if not submission:
        raise HTTPException(status_code=404, detail="No submission found for this paper")

    # Get correct answers
    correct_answers = db.query(models.MCQAnswer)\
        .filter(models.MCQAnswer.paper_id == paper_id)\
        .all()
    
    if not correct_answers:
        raise HTTPException(status_code=404, detail="No answers found for this paper")

    # Create a dictionary of correct answers
    correct_dict = {ans.question_number: ans.correct_option for ans in correct_answers}
    
    # Compare answers and create detailed response
    results = []
    total_correct = 0
    
    for answer in submission.answers:
        is_correct = (answer['question_number'] in correct_dict and 
                     correct_dict[answer['question_number']] == answer['selected_option'])
        
        results.append({
            "question_number": answer['question_number'],
            "selected_option": answer['selected_option'],
            "correct_option": correct_dict.get(answer['question_number']),
            "is_correct": is_correct
        })
        
        if is_correct:
            total_correct += 1

    return {
        "total_questions": len(correct_answers),
        "total_correct": total_correct,
        "score_percentage": (total_correct / len(correct_answers)) * 100,
        "detailed_results": results
    }


@app.post("/papers/{paper_id}/check-answers", response_model=schemas.PaperResult)
async def check_answers(
    paper_id: int,
    answers: dict,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Get correct answers from the database
    correct_answers = db.query(models.PaperAnswers).filter(
        models.PaperAnswers.paper_id == paper_id
    ).first()

    if not correct_answers:
        raise HTTPException(status_code=404, detail="Answer sheet not found")

    # Compare answers and calculate score
    score = 0
    answer_breakdown = []
    
    for question_num, user_answer in answers.items():
        correct = user_answer.lower() == correct_answers.answers.get(question_num, '').lower()
        if correct:
            score += 1
        answer_breakdown.append({
            "questionNumber": question_num,
            "userAnswer": user_answer,
            "correctAnswer": correct_answers.answers.get(question_num, ''),
            "correct": correct
        })

    # Save the result
    result = models.PaperSubmission(
        user_id=current_user.id,
        paper_id=paper_id,
        score=score,
        total_questions=len(answers),
        submitted_at=datetime.now()
    )
    db.add(result)
    db.commit()

    return {
        "score": score,
        "totalMarks": len(answers),
        "answers": answer_breakdown
    }




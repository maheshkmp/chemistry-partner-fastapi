# Remove duplicate imports
import os
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import jwt
from jwt.exceptions import PyJWTError
from typing import List
import shutil
from pathlib import Path
from database import create_tables, get_db, engine
import models
import schemas
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
import bcrypt
from fastapi import Request
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

# Single instance of FastAPI
app = FastAPI()

# Single CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single instance of configurations
SECRET_KEY = "123"
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
# Move validate_pdf_file before all route handlers
async def validate_pdf_file(file: UploadFile) -> bool:
    # Check file extension
    if not file.filename.lower().endswith('.pdf'):
        return False
    
    # Read first few bytes to verify PDF signature
    content = await file.read(5)
    await file.seek(0)  # Reset file pointer
    return content.startswith(b'%PDF-')

async def create_paper(
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
    
    return db_paper

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


@app.get("/papers/{paper_id}", response_model=schemas.Paper)
async def get_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_active_user)
):
    paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
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




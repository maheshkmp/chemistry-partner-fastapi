from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    submissions = relationship("Submission", back_populates="user")
    uploaded_files = relationship("File", back_populates="user")
    paper_submissions = relationship("PaperSubmission", back_populates="user")

class Paper(Base):
    __tablename__ = "papers"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    duration_minutes = Column(Integer)
    total_marks = Column(Integer)
    pdf_path = Column(String, nullable=True)  # Path to stored PDF file
    
    # All relationships in one place
    submissions = relationship("Submission", back_populates="paper")
    questions = relationship("Question", back_populates="paper")
    files = relationship("File", back_populates="paper", cascade="all, delete-orphan")
    mcq_answers = relationship("MCQAnswer", back_populates="paper", cascade="all, delete-orphan")
    paper_submissions = relationship("PaperSubmission", back_populates="paper")

class PaperSubmission(Base):
    __tablename__ = 'paper_submissions'

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    time_spent = Column(Integer)  # Time spent in seconds
    marks = Column(Integer)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    answers = Column(Text)  # Store answers as JSON string
    score = Column(Integer)  # Added score field

    # Relationships using back_populates consistently
    user = relationship("User", back_populates="paper_submissions")
    paper = relationship("Paper", back_populates="paper_submissions")

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"))
    question_text = Column(Text)
    answer = Column(String)
    marks = Column(Integer)
    
    paper = relationship("Paper", back_populates="questions")

class Submission(Base):
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    paper_id = Column(Integer, ForeignKey("papers.id"))
    score = Column(Integer)
    completed_at = Column(String)  # Store as ISO format datetime string
    
    user = relationship("User", back_populates="submissions")
    paper = relationship("Paper", back_populates="submissions")

class MCQAnswer(Base):
    __tablename__ = 'mcq_answers'

    id = Column(Integer, primary_key=True)
    paper_id = Column(Integer, ForeignKey('papers.id'))
    question_number = Column(Integer)
    correct_option = Column(String(1))

    paper = relationship("Paper", back_populates="mcq_answers")

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # 'pdf', 'excel', etc.
    upload_date = Column(DateTime, default=datetime.utcnow)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"))
    uploaded_by = Column(Integer, ForeignKey("users.id"))

    paper = relationship("Paper", back_populates="files")
    user = relationship("User", back_populates="uploaded_files")
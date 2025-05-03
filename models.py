from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    submissions = relationship("Submission", back_populates="user")

class Paper(Base):
    __tablename__ = "papers"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    duration_minutes = Column(Integer)
    total_marks = Column(Integer)
    pdf_path = Column(String, nullable=True)  # Path to stored PDF file
    
    submissions = relationship("Submission", back_populates="paper")
    questions = relationship("Question", back_populates="paper")

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

class PaperSubmission(Base):
    __tablename__ = "paper_submissions"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    time_spent = Column(Integer)  # Time spent in seconds
    marks = Column(Integer)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
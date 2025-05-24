from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class MCQAnswer(Base):
    __tablename__ = "mcq_answers"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"))
    question_number = Column(Integer)
    correct_option = Column(Integer)

    paper = relationship("Paper", back_populates="mcq_answers")
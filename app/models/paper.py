class Paper(Base):
    # ... existing columns ...
    
    mcq_answers = relationship("MCQAnswer", back_populates="paper", cascade="all, delete")
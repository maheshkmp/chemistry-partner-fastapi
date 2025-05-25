@router.post("/submit-paper/{paper_id}")
def submit_paper(paper_id: int, answers: dict, user_id: int, time_spent: int):
    # Convert answers to JSON string
    answers_json = json.dumps(answers)
    
    # Calculate marks
    total_marks = check_answers(paper_id, answers_json)
    
    # Create submission record
    submission = PaperSubmission(
        paper_id=paper_id,
        user_id=user_id,
        time_spent=time_spent,
        marks=total_marks,
        answers=answers_json
    )
    
    db.add(submission)
    db.commit()
    
    return {"marks": total_marks}
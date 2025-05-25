import json

def check_answers(paper_id, user_answers_json):
    """
    Check user answers against correct answers and calculate marks
    """
    total_marks = 0
    user_answers = json.loads(user_answers_json)
    
    # Get all questions for this paper
    questions = db.query(Question).filter(Question.paper_id == paper_id).all()
    mcq_answers = db.query(MCQAnswer).filter(MCQAnswer.paper_id == paper_id).all()
    
    # Check regular questions
    for question in questions:
        if str(question.id) in user_answers:
            if user_answers[str(question.id)].strip().lower() == question.answer.strip().lower():
                total_marks += question.marks
    
    # Check MCQ questions
    for mcq in mcq_answers:
        if str(mcq.question_number) in user_answers:
            if int(user_answers[str(mcq.question_number)]) == mcq.correct_option:
                # Assuming each MCQ has equal marks
                total_marks += 1
    
    return total_marks
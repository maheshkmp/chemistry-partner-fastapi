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
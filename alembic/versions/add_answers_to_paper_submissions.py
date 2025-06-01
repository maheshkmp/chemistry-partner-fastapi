"""add answers to paper submissions

Revision ID: add_answers_to_paper_submissions
Revises: create_mcq_answers
Create Date: 2024-01-09
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('paper_submissions',
        sa.Column('answers', sa.Text(), nullable=True)
    )

def downgrade():
    op.drop_column('paper_submissions', 'answers')
"""create mcq answers table

Revision ID: create_mcq_answers
Revises: previous_revision
Create Date: 2024-01-09
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'mcq_answers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('question_number', sa.Integer(), nullable=False),
        sa.Column('correct_option', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for faster lookups
    op.create_index('idx_mcq_answers_paper_id', 'mcq_answers', ['paper_id'])

def downgrade():
    op.drop_index('idx_mcq_answers_paper_id')
    op.drop_table('mcq_answers')
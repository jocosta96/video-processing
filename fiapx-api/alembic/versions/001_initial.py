"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-03
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    job_status = postgresql.ENUM(
        "UPLOADED", "QUEUED", "PROCESSING", "DONE", "FAILED", "CANCELLED", "EXPIRED",
        name="jobstatus",
    )
    job_status.create(op.get_bind())

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", postgresql.ENUM(name="jobstatus", create_type=False), nullable=False, server_default="UPLOADED"),
        sa.Column("video_path", sa.String(512), nullable=False),
        sa.Column("video_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("video_format", sa.String(10), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("zip_path", sa.String(512), nullable=True),
        sa.Column("frame_count", sa.Integer(), nullable=True),
        sa.Column("zip_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("processing_time_seconds", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_jobs_user_id", "jobs", ["user_id"])
    op.create_index("idx_jobs_status", "jobs", ["status"])

    op.create_table(
        "job_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("old_status", postgresql.ENUM(name="jobstatus", create_type=False), nullable=True),
        sa.Column("new_status", postgresql.ENUM(name="jobstatus", create_type=False), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_job_events_job_id", "job_events", ["job_id"])


def downgrade() -> None:
    op.drop_table("job_events")
    op.drop_table("jobs")
    op.drop_table("users")
    postgresql.ENUM(name="jobstatus").drop(op.get_bind())

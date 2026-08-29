"""Initial secure RAG schema."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    role = sa.Enum("analyst", "advisor", "admin", name="role")
    status = sa.Enum("processing", "ready", "failed", name="documentstatus")
    op.create_table("users", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("email", sa.String(320), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", role, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("documents", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("filename", sa.String(255), nullable=False), sa.Column("content_type", sa.String(100), nullable=False), sa.Column("checksum", sa.String(64), nullable=False), sa.Column("status", status, nullable=False), sa.Column("page_count", sa.Integer), sa.Column("error", sa.Text), sa.Column("metadata", sa.JSON, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_table("document_chunks", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False), sa.Column("ordinal", sa.Integer, nullable=False), sa.Column("page_number", sa.Integer), sa.Column("content", sa.Text, nullable=False), sa.Column("token_count", sa.Integer, nullable=False), sa.Column("embedding", Vector(1536), nullable=False), sa.Column("metadata", sa.JSON, nullable=False))
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_chunks_embedding_hnsw", "document_chunks", ["embedding"], postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"})
    op.create_table("generations", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("mode", sa.String(40), nullable=False), sa.Column("query", sa.Text, nullable=False), sa.Column("answer", sa.Text, nullable=False), sa.Column("citations", sa.JSON, nullable=False), sa.Column("model", sa.String(100), nullable=False), sa.Column("prompt_version", sa.String(40), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_generations_user_id", "generations", ["user_id"])
    op.create_table("audit_events", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("action", sa.String(100), nullable=False), sa.Column("resource_type", sa.String(60), nullable=False), sa.Column("resource_id", sa.String(100)), sa.Column("detail", sa.JSON, nullable=False), sa.Column("ip_address", sa.String(64)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("generations")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("users")
    sa.Enum(name="documentstatus").drop(op.get_bind())
    sa.Enum(name="role").drop(op.get_bind())

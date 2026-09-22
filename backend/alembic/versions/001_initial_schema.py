"""Initial database schema with pgvector and multi-tenancy

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-22 03:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. Orgs table
    op.create_table(
        "orgs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("plan_tier", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_orgs_slug", "orgs", ["slug"], unique=True)

    # 3. Org Members table
    op.create_table(
        "org_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "user_id", name="uq_org_member"),
    )
    op.create_index("ix_org_members_org_id", "org_members", ["org_id"])
    op.create_index("ix_org_members_user_id", "org_members", ["user_id"])

    # 4. Credit Ledger table (Append-only)
    op.create_table(
        "credit_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=50), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("search_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_credit_ledger_org_id", "credit_ledger", ["org_id"])
    op.create_index("ix_credit_ledger_search_id", "credit_ledger", ["search_id"])
    op.create_index("ix_credit_ledger_idempotency_key", "credit_ledger", ["idempotency_key"])
    op.create_index("ix_credit_ledger_created_at", "credit_ledger", ["created_at"])

    # 5. Searches table
    op.create_table(
        "searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("num_competitors", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("scope_override", sa.String(length=50), nullable=True, server_default="auto"),
        sa.Column("competitor_types", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued"),
        sa.Column("tier", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("actual_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("shortfall", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("shortfall_reason", sa.Text(), nullable=True),
        sa.Column("clarifying_question", sa.Text(), nullable=True),
        sa.Column("providers_used", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("profile_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_searches_org_id", "searches", ["org_id"])
    op.create_index("ix_searches_user_id", "searches", ["user_id"])
    op.create_index("ix_searches_status", "searches", ["status"])
    op.create_index("ix_searches_idempotency_key", "searches", ["idempotency_key"])
    op.create_index("ix_searches_created_at", "searches", ["created_at"])

    # 6. Search Results table
    op.create_table(
        "search_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("search_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("searches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("competitor_name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("competitor_type", sa.String(length=50), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_search_results_search_id", "search_results", ["search_id"])
    op.create_index("ix_search_results_org_id", "search_results", ["org_id"])
    op.create_index("ix_search_results_domain", "search_results", ["domain"])

    # 7. Market Companies table (pgvector embeddings with HNSW cosine index)
    op.create_table(
        "market_companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False, server_default="serpapi"),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("last_verified", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_market_companies_org_id", "market_companies", ["org_id"])
    op.create_index("ix_market_companies_name", "market_companies", ["name"])
    op.create_index("ix_market_companies_domain", "market_companies", ["domain"])
    op.create_index("ix_market_companies_category", "market_companies", ["category"])
    op.create_index("ix_market_companies_region", "market_companies", ["region"])
    op.create_index("ix_market_companies_category_region", "market_companies", ["category", "region"])
    op.create_index(
        "ix_market_companies_embedding_hnsw",
        "market_companies",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # 8. Feedback table
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("search_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("searches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("search_result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("search_results.id", ondelete="SET NULL"), nullable=True),
        sa.Column("feedback_type", sa.String(length=50), nullable=False),
        sa.Column("competitor_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_feedback_org_id", "feedback", ["org_id"])
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_search_id", "feedback", ["search_id"])
    op.create_index("ix_feedback_search_result_id", "feedback", ["search_result_id"])

    # 9. Provider Usage table
    op.create_table(
        "provider_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("search_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("searches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("call_type", sa.String(length=50), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_provider_usage_org_id", "provider_usage", ["org_id"])
    op.create_index("ix_provider_usage_search_id", "provider_usage", ["search_id"])
    op.create_index("ix_provider_usage_created_at", "provider_usage", ["created_at"])


def downgrade() -> None:
    op.drop_table("provider_usage")
    op.drop_table("feedback")
    op.drop_table("market_companies")
    op.drop_table("search_results")
    op.drop_table("searches")
    op.drop_table("credit_ledger")
    op.drop_table("org_members")
    op.drop_table("orgs")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector;")

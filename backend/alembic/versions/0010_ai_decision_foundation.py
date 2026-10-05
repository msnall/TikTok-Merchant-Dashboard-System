"""Phase 0 decision data foundation, independent of the existing ad status rules."""

from alembic import op
import sqlalchemy as sa


revision = "0010_ai_decision_foundation"
down_revision = "0009_script_timeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    new_tables = {"roi_policy_config", "campaign_video_metrics", "campaign_metric_timeseries",
                  "ai_analysis_runs", "ai_analysis_snapshots"}
    conflicts = existing & new_tables
    if conflicts:
        raise RuntimeError(f"迁移前存在无版本记录的同名表：{', '.join(sorted(conflicts))}；请先核对数据，不能自动覆盖")

    with op.batch_alter_table("ad_plan_snapshots") as batch:
        batch.add_column(sa.Column("report_date", sa.Date()))
        batch.add_column(sa.Column("report_start_at", sa.DateTime()))
        batch.add_column(sa.Column("report_end_at", sa.DateTime()))

    op.create_table(
        "roi_policy_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_code", sa.String(32), nullable=False, unique=True),
        sa.Column("policy_name", sa.String(80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.bulk_insert(sa.table("roi_policy_config", sa.column("policy_code"), sa.column("policy_name"),
                            sa.column("sort_order"), sa.column("description")), [
        {"policy_code": "break_even", "policy_name": "保本 ROI", "sort_order": 1,
         "description": "政策标签；具体目标数值由计划名或人工配置提供"},
        {"policy_code": "profit_5pct", "policy_name": "5% 利润 ROI", "sort_order": 2,
         "description": "政策标签；不在系统中推导利润公式"},
        {"policy_code": "profit_10pct", "policy_name": "10% 利润 ROI", "sort_order": 3,
         "description": "政策标签；具体目标数值待人工配置"},
    ])

    op.create_table(
        "campaign_video_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.String(64), nullable=False),
        sa.Column("video_id", sa.String(128), nullable=False),
        sa.Column("video_work_id", sa.Integer(), sa.ForeignKey("video_works.id", ondelete="SET NULL")),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("impressions", sa.Integer()), sa.Column("clicks", sa.Integer()),
        sa.Column("ctr", sa.Float()), sa.Column("orders", sa.Integer()),
        sa.Column("cvr", sa.Float()), sa.Column("spend", sa.Float()),
        sa.Column("revenue", sa.Float()), sa.Column("official_completion_rate", sa.Float()),
        sa.Column("source_field_name", sa.String(128)),
        sa.Column("source_document", sa.String(255)),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source_type IN ('uploaded_source', 'manual_entry', 'synthetic_demo')",
                           name="ck_campaign_video_source"),
    )
    op.create_table(
        "campaign_metric_timeseries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.String(64), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("spend", sa.Float(), nullable=False),
        sa.Column("orders", sa.Integer(), nullable=False),
        sa.Column("revenue", sa.Float(), nullable=False),
        sa.Column("measurement_type", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source_type IN ('uploaded_source', 'manual_entry', 'synthetic_demo')",
                           name="ck_campaign_timeseries_source"),
        sa.CheckConstraint("measurement_type IN ('cumulative', 'interval')", name="ck_timeseries_measurement"),
    )
    op.create_table(
        "ai_analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.String(64), nullable=False),
        sa.Column("analysis_time", sa.DateTime(), nullable=False),
        sa.Column("input_spend", sa.Float()), sa.Column("input_orders", sa.Integer()),
        sa.Column("input_revenue", sa.Float()), sa.Column("input_current_roi", sa.Float()),
        sa.Column("input_target_roi", sa.Float()), sa.Column("input_ctr", sa.Float()),
        sa.Column("input_cvr", sa.Float()), sa.Column("input_completion_rate", sa.Float()),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("rules_used", sa.Text(), nullable=False),
        sa.Column("facts", sa.Text(), nullable=False),
        sa.Column("recommendations", sa.Text(), nullable=False),
        sa.Column("uncertainties", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source_type IN ('uploaded_source', 'manual_entry', 'synthetic_demo')",
                           name="ck_analysis_run_source"),
    )
    op.create_table(
        "ai_analysis_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("ai_analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_data", sa.Text(), nullable=False),
        sa.Column("video_data", sa.Text(), nullable=False),
        sa.Column("source_information", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("run_id", name="uq_analysis_snapshot_run"),
    )
    for table, columns in {
        "campaign_video_metrics": ("campaign_id", "video_id", "report_date", "source_type"),
        "campaign_metric_timeseries": ("campaign_id", "timestamp", "source_type"),
        "ai_analysis_runs": ("campaign_id", "source_type"),
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table, columns in {
        "ai_analysis_runs": ("source_type", "campaign_id"),
        "campaign_metric_timeseries": ("source_type", "timestamp", "campaign_id"),
        "campaign_video_metrics": ("source_type", "report_date", "video_id", "campaign_id"),
    }.items():
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
    for table in ("ai_analysis_snapshots", "ai_analysis_runs", "campaign_metric_timeseries",
                  "campaign_video_metrics", "roi_policy_config"):
        op.drop_table(table)
    with op.batch_alter_table("ad_plan_snapshots") as batch:
        batch.drop_column("report_end_at")
        batch.drop_column("report_start_at")
        batch.drop_column("report_date")

"""Relational schema (SQLAlchemy Core) — the 9 tables from contracts/schema.md.

Defined with portable generic types so `metadata.create_all(engine)` emits correct DDL for
**both** SQLite (local/dev/test) and PostgreSQL (docker). JSON→JSONB on PG / TEXT on SQLite;
BigInteger PK→BIGSERIAL on PG / INTEGER autoincrement on SQLite.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, JSON, MetaData,
    Numeric, Table, Text, UniqueConstraint, func,
)

metadata = MetaData()

datasets = Table(
    "datasets", metadata,
    Column("dataset_id", BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True),
    Column("name", Text, nullable=False),
    Column("source", Text, nullable=False),            # upload | openml | import
    Column("openml_task_id", Integer),
    Column("task_type", Text),                         # binary | multiclass | regression
    Column("target_column", Text),
    Column("n_instances", Integer),
    Column("n_features", Integer),
    Column("n_classes", Integer),
    Column("minority_fraction", Numeric),
    Column("size_tier", Text),
    Column("file_format", Text),
    Column("storage_uri", Text),
    Column("checksum_sha256", Text),
    Column("status", Text, nullable=False, server_default="ready"),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("name", name="uq_datasets_name"),
)

methods = Table(
    "methods", metadata,
    Column("method_id", BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True),
    Column("name", Text, nullable=False, unique=True),
    Column("kind", Text),                              # automl | baseline
    Column("version", Text),
    Column("preset", Text),
    Column("integration_status", Text, server_default="available"),  # available|integrating|integrated|failed|setup_pending
    Column("docker_image", Text),
    Column("image_tag", Text),
    Column("image_digest", Text),
    Column("last_integration_at", DateTime(timezone=True)),
    Column("last_error", Text),
    Column("project_url", Text),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

constraints = Table(
    "constraints", metadata,
    Column("constraint_id", BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True),
    Column("name", Text, nullable=False, unique=True),
    Column("folds", Integer),
    Column("max_runtime_seconds", Integer),
    Column("cores", Integer),
    Column("max_mem_mb", Integer),
    Column("metric_by_type", JSON),
)

compute_instances = Table(
    "compute_instances", metadata,
    Column("instance_id", BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True),
    Column("name", Text, nullable=False),
    Column("vcpus", Integer),
    Column("memory_gb", Integer),
    Column("gpu_type", Text),
    Column("gpu_count", Integer, server_default="0"),
    Column("rate_per_hour", Numeric),
    Column("provider", Text),
    Column("active", Boolean, server_default="1"),
)

training_runs = Table(
    "training_runs", metadata,
    Column("training_run_id", BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True),
    Column("constraint_id", BigInteger, ForeignKey("constraints.constraint_id")),
    Column("instance_id", BigInteger, ForeignKey("compute_instances.instance_id")),
    Column("mode", Text),
    Column("status", Text, server_default="queued"),
    Column("est_cost", Numeric),
    Column("actual_cost", Numeric),
    Column("last_error", Text),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
)

runs = Table(
    "runs", metadata,
    Column("run_id", BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True),
    Column("training_run_id", BigInteger, ForeignKey("training_runs.training_run_id")),
    Column("dataset_id", BigInteger, ForeignKey("datasets.dataset_id")),
    Column("method_id", BigInteger, ForeignKey("methods.method_id")),
    Column("constraint_id", BigInteger, ForeignKey("constraints.constraint_id")),
    Column("fold", Integer),
    Column("metric", Text),
    Column("result", Numeric),
    Column("score", Numeric),
    Column("status", Text, nullable=False),            # success | failure_*
    Column("training_duration", Numeric),
    Column("predict_duration", Numeric),
    Column("models_count", Integer),
    Column("seed", BigInteger),
    Column("framework_version", Text),
    Column("metrics", JSON),
    Column("predictions_uri", Text),
    Column("error_message", Text),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

training_run_datasets = Table(
    "training_run_datasets", metadata,
    Column("training_run_id", BigInteger, ForeignKey("training_runs.training_run_id"), primary_key=True),
    Column("dataset_id", BigInteger, ForeignKey("datasets.dataset_id"), primary_key=True),
)

training_run_methods = Table(
    "training_run_methods", metadata,
    Column("training_run_id", BigInteger, ForeignKey("training_runs.training_run_id"), primary_key=True),
    Column("method_id", BigInteger, ForeignKey("methods.method_id"), primary_key=True),
)

deployments = Table(
    "deployments", metadata,
    Column("deployment_id", BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True),
    Column("run_id", BigInteger, ForeignKey("runs.run_id")),
    Column("instance_id", BigInteger, ForeignKey("compute_instances.instance_id")),
    Column("endpoint_url", Text),
    Column("status", Text),
    Column("model_uri", Text),
    Column("p95_latency_ms", Numeric),
    Column("deployed_at", DateTime(timezone=True)),
)

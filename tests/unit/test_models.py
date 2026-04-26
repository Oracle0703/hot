from sqlalchemy.orm import configure_mappers

from app.models.content_item import ContentItem
from app.models.delivery_record import DeliveryRecord
from app.models.item import CollectedItem
from app.models.job import CollectionJob
from app.models.raw_item import RawItem
from app.models.report import Report
from app.models.schedule_plan import SchedulePlan
from app.models.subscription import Subscription
from app.models.source import Source


def test_source_model_requires_core_fields() -> None:
    columns = Source.__table__.columns

    assert columns["name"].nullable is False
    assert columns["entry_url"].nullable is False
    assert columns["fetch_mode"].nullable is False
    assert "source_group" in columns
    assert "schedule_group" in columns
    assert columns["enabled"].default.arg is True


def test_collection_job_status_defaults_to_pending() -> None:
    status_column = CollectionJob.__table__.columns["status"]

    assert status_column.default.arg == "pending"
    assert "source_group_scope" in CollectionJob.__table__.columns
    assert "schedule_group_scope" in CollectionJob.__table__.columns


def test_schedule_plan_model_keeps_required_columns() -> None:
    columns = SchedulePlan.__table__.columns

    assert columns["enabled"].nullable is False
    assert "run_time" in columns
    assert "schedule_group" in columns
    assert "last_triggered_on" in columns


def test_collected_item_has_unique_normalized_hash() -> None:
    unique_constraints = list(CollectedItem.__table__.constraints)

    assert any(
        constraint.__class__.__name__ == "UniqueConstraint"
        and [column.name for column in constraint.columns] == ["normalized_hash"]
        for constraint in unique_constraints
    )


def test_collected_item_tracks_first_and_last_seen_fields() -> None:
    columns = CollectedItem.__table__.columns

    assert "first_seen_at" in columns
    assert "last_seen_at" in columns
    assert "first_seen_job_id" in columns
    assert "last_seen_job_id" in columns
    assert "image_urls" in columns
    assert "cover_image_url" in columns
    assert "like_count" in columns
    assert "reply_count" in columns
    assert "view_count" in columns
    assert "recommended_grade" in columns
    assert "manual_grade" in columns
    assert "pushed_to_dingtalk_at" in columns
    assert "pushed_to_dingtalk_batch_id" in columns
    assert columns["first_seen_job_id"].nullable is True
    assert columns["last_seen_job_id"].nullable is True
    assert len(columns["first_seen_job_id"].foreign_keys) == 1
    assert len(columns["last_seen_job_id"].foreign_keys) == 1
    assert next(iter(columns["first_seen_job_id"].foreign_keys)).target_fullname == "collection_jobs.id"
    assert next(iter(columns["last_seen_job_id"].foreign_keys)).target_fullname == "collection_jobs.id"


def test_report_belongs_to_collection_job() -> None:
    job_id_column = Report.__table__.columns["job_id"]
    foreign_keys = job_id_column.foreign_keys

    assert job_id_column.nullable is False
    assert len(foreign_keys) == 1
    assert next(iter(foreign_keys)).target_fullname == "collection_jobs.id"


def test_report_keeps_core_columns_for_global_report() -> None:
    columns = Report.__table__.columns

    assert "id" in columns
    assert "job_id" in columns
    assert "markdown_path" in columns
    assert "docx_path" in columns
    assert "created_at" in columns


def test_collection_job_items_relationship_maps_to_item_job_id() -> None:
    configure_mappers()
    relationship_property = CollectionJob.__mapper__.relationships["items"]

    assert CollectedItem.__table__.columns["job_id"] in relationship_property._calculated_foreign_keys


def test_collected_item_job_relationship_maps_to_job_id_only() -> None:
    configure_mappers()
    relationship_property = CollectedItem.__mapper__.relationships["job"]

    assert CollectedItem.__table__.columns["job_id"] in relationship_property._calculated_foreign_keys


def test_raw_item_belongs_to_source_and_job() -> None:
    columns = RawItem.__table__.columns

    assert columns["source_id"].nullable is False
    assert columns["job_id"].nullable is False
    assert "payload" in columns


def test_content_item_uses_unique_dedupe_key() -> None:
    columns = ContentItem.__table__.columns
    unique_constraints = list(ContentItem.__table__.constraints)

    assert columns["dedupe_key"].nullable is False
    assert columns["canonical_url"].nullable is False
    assert any(
        constraint.__class__.__name__ == "UniqueConstraint"
        and [column.name for column in constraint.columns] == ["dedupe_key"]
        for constraint in unique_constraints
    )


def test_subscription_and_delivery_record_keep_core_columns() -> None:
    subscription_columns = Subscription.__table__.columns
    delivery_columns = DeliveryRecord.__table__.columns

    assert subscription_columns["code"].nullable is False
    assert subscription_columns["channel"].nullable is False
    assert "business_lines" in subscription_columns
    assert "keywords" in subscription_columns
    assert delivery_columns["subscription_id"].nullable is False
    assert delivery_columns["content_item_id"].nullable is False
    assert delivery_columns["status"].nullable is False
    assert "error_message" in delivery_columns
    assert delivery_columns["error_message"].nullable is True


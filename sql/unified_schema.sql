PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_system (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    base_url TEXT,
    license_name TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingestion_run (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    pipeline_stage TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    raw_path TEXT,
    record_count INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    FOREIGN KEY (source_id) REFERENCES source_system(source_id)
);

CREATE TABLE IF NOT EXISTS dataset (
    dataset_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    dataset_code TEXT NOT NULL UNIQUE,
    dataset_name TEXT NOT NULL,
    task_type TEXT,
    homepage_url TEXT,
    license_name TEXT,
    local_path TEXT,
    manifest_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES source_system(source_id)
);

CREATE TABLE IF NOT EXISTS dataset_version (
    dataset_version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL,
    version_tag TEXT NOT NULL,
    released_at TEXT,
    split_schema_json TEXT,
    note TEXT,
    UNIQUE (dataset_id, version_tag),
    FOREIGN KEY (dataset_id) REFERENCES dataset(dataset_id)
);

CREATE TABLE IF NOT EXISTS source_record (
    source_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    source_entity_type TEXT NOT NULL,
    source_entity_id TEXT NOT NULL,
    canonical_table TEXT,
    canonical_id INTEGER,
    raw_payload_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, source_entity_type, source_entity_id),
    FOREIGN KEY (run_id) REFERENCES ingestion_run(run_id)
);

CREATE TABLE IF NOT EXISTS dataset_annotation_record (
    dataset_annotation_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_version_id INTEGER NOT NULL,
    source_record_id INTEGER,
    sample_key TEXT NOT NULL,
    image_rel_path TEXT,
    annotation_type TEXT NOT NULL,
    category TEXT,
    source_pose TEXT,
    target_pose TEXT,
    mirror_flag TEXT,
    viewpoint_variation REAL,
    bounding_box_json TEXT,
    points_json TEXT,
    payload_json TEXT,
    UNIQUE (dataset_version_id, sample_key, annotation_type, image_rel_path),
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_version(dataset_version_id),
    FOREIGN KEY (source_record_id) REFERENCES source_record(source_record_id)
);

CREATE TABLE IF NOT EXISTS dataset_text_description (
    dataset_text_description_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_version_id INTEGER NOT NULL,
    source_record_id INTEGER,
    sample_key TEXT,
    image_rel_path TEXT,
    description_source TEXT NOT NULL,
    length_label TEXT,
    vibe_label TEXT,
    style_label TEXT,
    description_text TEXT NOT NULL,
    payload_json TEXT,
    UNIQUE (dataset_version_id, description_source, sample_key, image_rel_path, description_text),
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_version(dataset_version_id),
    FOREIGN KEY (source_record_id) REFERENCES source_record(source_record_id)
);

CREATE TABLE IF NOT EXISTS dataset_feature_record (
    dataset_feature_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_version_id INTEGER NOT NULL,
    source_record_id INTEGER,
    sample_key TEXT,
    image_rel_path TEXT,
    feature_group TEXT,
    feature_name TEXT NOT NULL,
    feature_value_text TEXT,
    feature_value_num REAL,
    unit_text TEXT,
    payload_json TEXT,
    UNIQUE (dataset_version_id, sample_key, image_rel_path, feature_group, feature_name, feature_value_text),
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_version(dataset_version_id),
    FOREIGN KEY (source_record_id) REFERENCES source_record(source_record_id)
);

CREATE TABLE IF NOT EXISTS media_asset (
    media_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    asset_type TEXT NOT NULL,
    original_url TEXT,
    local_path TEXT,
    sha256 TEXT,
    mime_type TEXT,
    width INTEGER,
    height INTEGER,
    captured_at TEXT,
    metadata_json TEXT,
    UNIQUE (original_url, local_path),
    FOREIGN KEY (source_id) REFERENCES source_system(source_id)
);

CREATE TABLE IF NOT EXISTS image_item (
    image_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_version_id INTEGER,
    media_id INTEGER NOT NULL UNIQUE,
    split_name TEXT,
    image_role TEXT,
    scene_type TEXT,
    is_side_view INTEGER NOT NULL DEFAULT 0,
    quality_score REAL,
    license_name TEXT,
    source_record_key TEXT,
    captured_at TEXT,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_version(dataset_version_id),
    FOREIGN KEY (media_id) REFERENCES media_asset(media_id)
);

CREATE TABLE IF NOT EXISTS bicycle_instance (
    bicycle_instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    instance_index INTEGER NOT NULL DEFAULT 1,
    is_primary INTEGER NOT NULL DEFAULT 1,
    view_label TEXT,
    occlusion_level TEXT,
    truncation_level TEXT,
    bbox_x REAL,
    bbox_y REAL,
    bbox_width REAL,
    bbox_height REAL,
    UNIQUE (image_id, instance_index),
    FOREIGN KEY (image_id) REFERENCES image_item(image_id)
);

CREATE TABLE IF NOT EXISTS annotation_task (
    annotation_task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_version_id INTEGER,
    task_name TEXT NOT NULL,
    tool_name TEXT,
    annotation_type TEXT NOT NULL,
    label_schema_json TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_version(dataset_version_id)
);

CREATE TABLE IF NOT EXISTS annotation_set (
    annotation_set_id INTEGER PRIMARY KEY AUTOINCREMENT,
    annotation_task_id INTEGER NOT NULL,
    image_id INTEGER NOT NULL,
    annotator TEXT,
    reviewer TEXT,
    annotation_format TEXT,
    annotation_uri TEXT,
    quality_status TEXT,
    version_no INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (annotation_task_id, image_id, version_no),
    FOREIGN KEY (annotation_task_id) REFERENCES annotation_task(annotation_task_id),
    FOREIGN KEY (image_id) REFERENCES image_item(image_id)
);

CREATE TABLE IF NOT EXISTS part_taxonomy (
    part_taxonomy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_part_taxonomy_id INTEGER,
    part_key TEXT NOT NULL UNIQUE,
    part_name TEXT NOT NULL,
    part_level INTEGER NOT NULL DEFAULT 1,
    visualization_slot TEXT,
    description TEXT,
    FOREIGN KEY (parent_part_taxonomy_id) REFERENCES part_taxonomy(part_taxonomy_id)
);

CREATE TABLE IF NOT EXISTS annotated_object (
    annotated_object_id INTEGER PRIMARY KEY AUTOINCREMENT,
    annotation_set_id INTEGER NOT NULL,
    bicycle_instance_id INTEGER,
    part_taxonomy_id INTEGER,
    object_class TEXT NOT NULL,
    geometry_type TEXT NOT NULL,
    area_value REAL,
    is_crowd INTEGER NOT NULL DEFAULT 0,
    visibility TEXT,
    bbox_x REAL,
    bbox_y REAL,
    bbox_width REAL,
    bbox_height REAL,
    attributes_json TEXT,
    FOREIGN KEY (annotation_set_id) REFERENCES annotation_set(annotation_set_id),
    FOREIGN KEY (bicycle_instance_id) REFERENCES bicycle_instance(bicycle_instance_id),
    FOREIGN KEY (part_taxonomy_id) REFERENCES part_taxonomy(part_taxonomy_id)
);

CREATE TABLE IF NOT EXISTS object_geometry (
    object_geometry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    annotated_object_id INTEGER NOT NULL,
    geometry_kind TEXT NOT NULL,
    geometry_json TEXT,
    mask_rle TEXT,
    keypoints_json TEXT,
    polygon_count INTEGER,
    FOREIGN KEY (annotated_object_id) REFERENCES annotated_object(annotated_object_id)
);

CREATE TABLE IF NOT EXISTS brand (
    brand_id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name TEXT NOT NULL UNIQUE,
    brand_slug TEXT NOT NULL UNIQUE,
    brand_type TEXT,
    official_site_url TEXT,
    country_code TEXT
);

CREATE TABLE IF NOT EXISTS bike_family (
    bike_family_id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NOT NULL,
    family_name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    UNIQUE (brand_id, family_name),
    FOREIGN KEY (brand_id) REFERENCES brand(brand_id)
);

CREATE TABLE IF NOT EXISTS bike_model (
    bike_model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bike_family_id INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    model_year INTEGER,
    gender_group TEXT,
    wheel_size_text TEXT,
    frame_material TEXT,
    source_confidence REAL,
    UNIQUE (bike_family_id, model_name, model_year),
    FOREIGN KEY (bike_family_id) REFERENCES bike_family(bike_family_id)
);

CREATE TABLE IF NOT EXISTS bike_variant (
    bike_variant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bike_model_id INTEGER NOT NULL,
    variant_name TEXT NOT NULL,
    colorway TEXT,
    msrp_value REAL,
    currency TEXT,
    official_url TEXT,
    lifecycle_status TEXT,
    description TEXT,
    payload_json TEXT,
    UNIQUE (bike_model_id, variant_name),
    FOREIGN KEY (bike_model_id) REFERENCES bike_model(bike_model_id)
);

CREATE TABLE IF NOT EXISTS bike_variant_alias (
    bike_variant_alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bike_variant_id INTEGER NOT NULL,
    alias_text TEXT NOT NULL,
    alias_slug TEXT NOT NULL,
    alias_type TEXT NOT NULL DEFAULT 'name',
    source_id INTEGER,
    source_entity_id TEXT,
    UNIQUE (bike_variant_id, alias_slug, alias_type),
    FOREIGN KEY (bike_variant_id) REFERENCES bike_variant(bike_variant_id),
    FOREIGN KEY (source_id) REFERENCES source_system(source_id)
);

CREATE TABLE IF NOT EXISTS bike_variant_spec (
    bike_variant_spec_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bike_variant_id INTEGER NOT NULL,
    spec_group TEXT,
    spec_name TEXT NOT NULL,
    spec_value TEXT,
    source_priority INTEGER NOT NULL DEFAULT 1,
    UNIQUE (bike_variant_id, spec_group, spec_name, spec_value),
    FOREIGN KEY (bike_variant_id) REFERENCES bike_variant(bike_variant_id)
);

CREATE TABLE IF NOT EXISTS component_catalog (
    component_catalog_id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER,
    part_taxonomy_id INTEGER,
    component_name TEXT NOT NULL,
    canonical_key TEXT NOT NULL UNIQUE,
    component_category TEXT,
    series_name TEXT,
    model_code TEXT,
    official_url TEXT,
    description TEXT,
    payload_json TEXT,
    FOREIGN KEY (brand_id) REFERENCES brand(brand_id),
    FOREIGN KEY (part_taxonomy_id) REFERENCES part_taxonomy(part_taxonomy_id)
);

CREATE TABLE IF NOT EXISTS component_catalog_alias (
    component_catalog_alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_catalog_id INTEGER NOT NULL,
    alias_text TEXT NOT NULL,
    alias_slug TEXT NOT NULL,
    alias_type TEXT NOT NULL DEFAULT 'name',
    source_id INTEGER,
    source_entity_id TEXT,
    UNIQUE (component_catalog_id, alias_slug, alias_type),
    FOREIGN KEY (component_catalog_id) REFERENCES component_catalog(component_catalog_id),
    FOREIGN KEY (source_id) REFERENCES source_system(source_id)
);

CREATE TABLE IF NOT EXISTS component_catalog_spec (
    component_catalog_spec_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_catalog_id INTEGER NOT NULL,
    spec_group TEXT,
    spec_name TEXT NOT NULL,
    spec_value TEXT,
    source_priority INTEGER NOT NULL DEFAULT 1,
    UNIQUE (component_catalog_id, spec_group, spec_name, spec_value),
    FOREIGN KEY (component_catalog_id) REFERENCES component_catalog(component_catalog_id)
);

CREATE TABLE IF NOT EXISTS bike_build_component (
    bike_build_component_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bike_variant_id INTEGER NOT NULL,
    part_taxonomy_id INTEGER NOT NULL,
    component_catalog_id INTEGER,
    slot_name TEXT NOT NULL,
    spec_name TEXT,
    spec_value TEXT,
    inferred_brand_text TEXT,
    source_priority INTEGER NOT NULL DEFAULT 1,
    UNIQUE (bike_variant_id, slot_name, spec_name, spec_value),
    FOREIGN KEY (bike_variant_id) REFERENCES bike_variant(bike_variant_id),
    FOREIGN KEY (part_taxonomy_id) REFERENCES part_taxonomy(part_taxonomy_id),
    FOREIGN KEY (component_catalog_id) REFERENCES component_catalog(component_catalog_id)
);

CREATE TABLE IF NOT EXISTS bike_media (
    bike_media_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bike_variant_id INTEGER NOT NULL,
    media_id INTEGER NOT NULL,
    view_type TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 1,
    UNIQUE (bike_variant_id, media_id, view_type),
    FOREIGN KEY (bike_variant_id) REFERENCES bike_variant(bike_variant_id),
    FOREIGN KEY (media_id) REFERENCES media_asset(media_id)
);

CREATE TABLE IF NOT EXISTS component_media (
    component_media_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_catalog_id INTEGER NOT NULL,
    media_id INTEGER NOT NULL,
    view_type TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 1,
    UNIQUE (component_catalog_id, media_id, view_type),
    FOREIGN KEY (component_catalog_id) REFERENCES component_catalog(component_catalog_id),
    FOREIGN KEY (media_id) REFERENCES media_asset(media_id)
);

CREATE TABLE IF NOT EXISTS merchant (
    merchant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_name TEXT NOT NULL UNIQUE,
    site_url TEXT,
    country_code TEXT
);

CREATE TABLE IF NOT EXISTS offer_snapshot (
    offer_snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    merchant_id INTEGER,
    component_catalog_id INTEGER,
    bike_variant_id INTEGER,
    source_entity_id TEXT,
    offer_title TEXT NOT NULL,
    offer_category TEXT,
    price_value REAL,
    currency TEXT,
    stock_status TEXT,
    item_condition TEXT,
    offer_url TEXT,
    observed_at TEXT NOT NULL,
    payload_json TEXT,
    CHECK (component_catalog_id IS NOT NULL OR bike_variant_id IS NOT NULL),
    FOREIGN KEY (source_id) REFERENCES source_system(source_id),
    FOREIGN KEY (merchant_id) REFERENCES merchant(merchant_id),
    FOREIGN KEY (component_catalog_id) REFERENCES component_catalog(component_catalog_id),
    FOREIGN KEY (bike_variant_id) REFERENCES bike_variant(bike_variant_id)
);

CREATE TABLE IF NOT EXISTS review_article (
    review_article_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    author_name TEXT,
    published_at TEXT,
    summary TEXT,
    rating_value REAL,
    rating_scale REAL,
    sentiment_score REAL,
    review_url TEXT,
    payload_json TEXT,
    FOREIGN KEY (source_id) REFERENCES source_system(source_id)
);

CREATE TABLE IF NOT EXISTS review_target (
    review_target_id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_article_id INTEGER NOT NULL,
    brand_id INTEGER,
    bike_variant_id INTEGER,
    component_catalog_id INTEGER,
    match_confidence REAL,
    CHECK (
        brand_id IS NOT NULL
        OR bike_variant_id IS NOT NULL
        OR component_catalog_id IS NOT NULL
    ),
    FOREIGN KEY (review_article_id) REFERENCES review_article(review_article_id),
    FOREIGN KEY (brand_id) REFERENCES brand(brand_id),
    FOREIGN KEY (bike_variant_id) REFERENCES bike_variant(bike_variant_id),
    FOREIGN KEY (component_catalog_id) REFERENCES component_catalog(component_catalog_id)
);

CREATE TABLE IF NOT EXISTS source_entity_map (
    source_entity_map_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    source_entity_type TEXT NOT NULL,
    source_entity_id TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    match_confidence REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_id, source_entity_type, source_entity_id, target_table, target_id),
    FOREIGN KEY (source_id) REFERENCES source_system(source_id)
);

CREATE TABLE IF NOT EXISTS image_bike_variant_map (
    image_bike_variant_map_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bicycle_instance_id INTEGER NOT NULL,
    bike_variant_id INTEGER NOT NULL,
    match_confidence REAL,
    match_method TEXT,
    UNIQUE (bicycle_instance_id, bike_variant_id),
    FOREIGN KEY (bicycle_instance_id) REFERENCES bicycle_instance(bicycle_instance_id),
    FOREIGN KEY (bike_variant_id) REFERENCES bike_variant(bike_variant_id)
);

CREATE TABLE IF NOT EXISTS bike_part_metric_snapshot (
    bike_part_metric_snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bike_variant_id INTEGER NOT NULL,
    part_taxonomy_id INTEGER NOT NULL,
    component_catalog_id INTEGER,
    snapshot_date TEXT NOT NULL,
    offer_count INTEGER NOT NULL DEFAULT 0,
    review_count INTEGER NOT NULL DEFAULT 0,
    avg_price REAL,
    avg_rating REAL,
    price_score REAL,
    quality_score REAL,
    value_score REAL,
    confidence_score REAL,
    metric_json TEXT,
    UNIQUE (bike_variant_id, part_taxonomy_id, snapshot_date),
    FOREIGN KEY (bike_variant_id) REFERENCES bike_variant(bike_variant_id),
    FOREIGN KEY (part_taxonomy_id) REFERENCES part_taxonomy(part_taxonomy_id),
    FOREIGN KEY (component_catalog_id) REFERENCES component_catalog(component_catalog_id)
);

CREATE TABLE IF NOT EXISTS component_metric_snapshot (
    component_metric_snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_catalog_id INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL,
    offer_count INTEGER NOT NULL DEFAULT 0,
    review_count INTEGER NOT NULL DEFAULT 0,
    avg_price REAL,
    avg_rating REAL,
    price_score REAL,
    quality_score REAL,
    value_score REAL,
    confidence_score REAL,
    metric_json TEXT,
    UNIQUE (component_catalog_id, snapshot_date),
    FOREIGN KEY (component_catalog_id) REFERENCES component_catalog(component_catalog_id)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_run_source
    ON ingestion_run(source_id, started_at);

CREATE INDEX IF NOT EXISTS idx_dataset_version_dataset
    ON dataset_version(dataset_id);

CREATE INDEX IF NOT EXISTS idx_source_record_run
    ON source_record(run_id, source_entity_type);

CREATE INDEX IF NOT EXISTS idx_dataset_annotation_record_dataset
    ON dataset_annotation_record(dataset_version_id, annotation_type, sample_key);

CREATE INDEX IF NOT EXISTS idx_dataset_text_description_dataset
    ON dataset_text_description(dataset_version_id, description_source, sample_key);

CREATE INDEX IF NOT EXISTS idx_dataset_feature_record_dataset
    ON dataset_feature_record(dataset_version_id, feature_group, feature_name, sample_key);

CREATE INDEX IF NOT EXISTS idx_image_item_dataset
    ON image_item(dataset_version_id, split_name, is_side_view);

CREATE INDEX IF NOT EXISTS idx_bicycle_instance_image
    ON bicycle_instance(image_id);

CREATE INDEX IF NOT EXISTS idx_annotation_set_image
    ON annotation_set(image_id, version_no);

CREATE INDEX IF NOT EXISTS idx_annotated_object_part
    ON annotated_object(part_taxonomy_id, object_class);

CREATE INDEX IF NOT EXISTS idx_component_catalog_taxonomy
    ON component_catalog(part_taxonomy_id, component_category);

CREATE INDEX IF NOT EXISTS idx_bike_variant_alias_lookup
    ON bike_variant_alias(alias_slug, alias_type);

CREATE INDEX IF NOT EXISTS idx_component_catalog_alias_lookup
    ON component_catalog_alias(alias_slug, alias_type);

CREATE INDEX IF NOT EXISTS idx_bike_build_component_variant
    ON bike_build_component(bike_variant_id, part_taxonomy_id);

CREATE INDEX IF NOT EXISTS idx_offer_snapshot_component
    ON offer_snapshot(component_catalog_id, observed_at, price_value);

CREATE INDEX IF NOT EXISTS idx_offer_snapshot_bike
    ON offer_snapshot(bike_variant_id, observed_at, price_value);

CREATE INDEX IF NOT EXISTS idx_review_target_component
    ON review_target(component_catalog_id);

CREATE INDEX IF NOT EXISTS idx_review_target_bike
    ON review_target(bike_variant_id);

CREATE INDEX IF NOT EXISTS idx_bike_part_metric_snapshot
    ON bike_part_metric_snapshot(bike_variant_id, snapshot_date);

CREATE INDEX IF NOT EXISTS idx_component_metric_snapshot
    ON component_metric_snapshot(component_catalog_id, snapshot_date);

CREATE VIEW IF NOT EXISTS vw_bike_core AS
SELECT
    bv.bike_variant_id,
    br.brand_name,
    bf.family_name,
    bm.model_name,
    bm.model_year,
    bv.variant_name,
    bv.colorway,
    bv.msrp_value,
    bv.currency,
    bv.official_url,
    bv.lifecycle_status,
    bv.description
FROM bike_variant AS bv
JOIN bike_model AS bm
    ON bm.bike_model_id = bv.bike_model_id
JOIN bike_family AS bf
    ON bf.bike_family_id = bm.bike_family_id
JOIN brand AS br
    ON br.brand_id = bf.brand_id;

CREATE VIEW IF NOT EXISTS vw_component_core AS
SELECT
    cc.component_catalog_id,
    br.brand_name,
    pt.part_key,
    pt.part_name,
    cc.component_name,
    cc.canonical_key,
    cc.component_category,
    cc.series_name,
    cc.model_code,
    cc.official_url,
    cc.description
FROM component_catalog AS cc
LEFT JOIN brand AS br
    ON br.brand_id = cc.brand_id
LEFT JOIN part_taxonomy AS pt
    ON pt.part_taxonomy_id = cc.part_taxonomy_id;

CREATE VIEW IF NOT EXISTS vw_bike_part_heatmap AS
SELECT
    bpm.bike_variant_id,
    pt.part_key,
    pt.part_name,
    bpm.snapshot_date,
    bpm.offer_count,
    bpm.review_count,
    bpm.avg_price,
    bpm.avg_rating,
    bpm.price_score,
    bpm.quality_score,
    bpm.value_score,
    bpm.confidence_score,
    cc.component_name
FROM bike_part_metric_snapshot AS bpm
JOIN part_taxonomy AS pt
    ON pt.part_taxonomy_id = bpm.part_taxonomy_id
LEFT JOIN component_catalog AS cc
    ON cc.component_catalog_id = bpm.component_catalog_id;

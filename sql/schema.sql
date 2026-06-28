PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS dataset_manifest (
    dataset_name TEXT,
    source_url TEXT,
    local_path TEXT,
    status TEXT,
    detail TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS source_runs (
    source_name TEXT,
    run_at TEXT,
    raw_file TEXT,
    record_count INTEGER
);

CREATE TABLE IF NOT EXISTS bikes (
    source TEXT,
    source_id TEXT,
    title TEXT,
    manufacturer TEXT,
    frame_model TEXT,
    year INTEGER,
    description TEXT,
    category TEXT,
    price_text TEXT,
    rating_text TEXT,
    url TEXT,
    payload_json TEXT,
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS components (
    source TEXT,
    source_id TEXT,
    name TEXT,
    manufacturer TEXT,
    category TEXT,
    price_text TEXT,
    price_value REAL,
    currency TEXT,
    rating_text TEXT,
    rating_value REAL,
    review_count INTEGER,
    url TEXT,
    payload_json TEXT,
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS reviews (
    source TEXT,
    source_id TEXT,
    title TEXT,
    summary TEXT,
    category TEXT,
    subtype TEXT,
    brand_hint TEXT,
    price_text TEXT,
    price_value REAL,
    url TEXT,
    payload_json TEXT,
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS manufacturers (
    source TEXT,
    source_id TEXT,
    name TEXT,
    slug TEXT,
    url TEXT,
    payload_json TEXT,
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS official_bikes (
    source TEXT,
    source_id TEXT,
    brand TEXT,
    bike_name TEXT,
    bike_url TEXT,
    price_text TEXT,
    description TEXT,
    front_view_url TEXT,
    side_view_url TEXT,
    rear_view_url TEXT,
    payload_json TEXT,
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS official_bike_components (
    bike_source TEXT,
    bike_source_id TEXT,
    component_order INTEGER,
    component_name TEXT,
    component_value TEXT,
    normalized_component_key TEXT,
    inferred_brand TEXT,
    PRIMARY KEY (bike_source, bike_source_id, component_order)
);

CREATE TABLE IF NOT EXISTS official_bike_specs (
    bike_source TEXT,
    bike_source_id TEXT,
    spec_order INTEGER,
    spec_name TEXT,
    spec_value TEXT,
    PRIMARY KEY (bike_source, bike_source_id, spec_order)
);

CREATE TABLE IF NOT EXISTS component_market_offers (
    component_key TEXT,
    matched_component_name TEXT,
    offer_source TEXT,
    offer_source_id TEXT,
    offer_title TEXT,
    manufacturer TEXT,
    category TEXT,
    price_text TEXT,
    price_value REAL,
    currency TEXT,
    url TEXT,
    payload_json TEXT,
    PRIMARY KEY (component_key, offer_source, offer_source_id)
);

CREATE TABLE IF NOT EXISTS component_quality_reviews (
    component_key TEXT,
    review_source TEXT,
    review_source_id TEXT,
    review_title TEXT,
    brand_hint TEXT,
    category TEXT,
    subtype TEXT,
    rating_text TEXT,
    rating_value REAL,
    summary TEXT,
    url TEXT,
    payload_json TEXT,
    PRIMARY KEY (component_key, review_source, review_source_id)
);

CREATE TABLE IF NOT EXISTS official_bike_rows (
    source TEXT,
    source_id TEXT,
    brand TEXT,
    bike_name TEXT,
    bike_url TEXT,
    front_view_url TEXT,
    side_view_url TEXT,
    rear_view_url TEXT,
    component_table_json TEXT,
    price_quality_summary_json TEXT,
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS official_components (
    source TEXT,
    source_id TEXT,
    brand TEXT,
    component_name TEXT,
    component_url TEXT,
    component_category TEXT,
    price_text TEXT,
    description TEXT,
    image_url TEXT,
    payload_json TEXT,
    PRIMARY KEY (source, source_id)
);

CREATE TABLE IF NOT EXISTS official_component_specs (
    component_source TEXT,
    component_source_id TEXT,
    spec_order INTEGER,
    spec_name TEXT,
    spec_value TEXT,
    PRIMARY KEY (component_source, component_source_id, spec_order)
);

CREATE TABLE IF NOT EXISTS official_component_rows (
    source TEXT,
    source_id TEXT,
    brand TEXT,
    component_name TEXT,
    component_url TEXT,
    component_category TEXT,
    image_url TEXT,
    specs_json TEXT,
    market_offers_json TEXT,
    quality_reviews_json TEXT,
    PRIMARY KEY (source, source_id)
);

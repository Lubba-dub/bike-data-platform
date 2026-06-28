# 扩容后数据库数据字典与表间关系说明

本文档描述统一数据库 `data/gold/bicycle_unified_warehouse.db` 的当前主结构，重点覆盖：

- 公开源抓取层
- 开源数据集层
- 视觉标注层
- 自行车/配件业务实体层
- 报价/评测事实层
- 热力图指标层

## 1. 总体关系主线

```text
source_system
  └─ ingestion_run
      └─ source_record

source_system
  └─ dataset
      └─ dataset_version
          ├─ image_item
          │   └─ bicycle_instance
          │       ├─ annotation_set
          │       │   └─ annotated_object
          │       │       └─ object_geometry
          │       └─ image_bike_variant_map
          ├─ dataset_annotation_record
          ├─ dataset_text_description
          └─ dataset_feature_record

brand
  └─ bike_family
      └─ bike_model
          └─ bike_variant
              ├─ bike_variant_spec
              ├─ bike_build_component
              ├─ bike_media
              └─ bike_part_metric_snapshot

part_taxonomy
  ├─ component_catalog
  │   ├─ component_catalog_spec
  │   ├─ component_media
  │   ├─ offer_snapshot
  │   ├─ review_target
  │   └─ component_metric_snapshot
  ├─ bike_build_component
  ├─ annotated_object
  └─ bike_part_metric_snapshot

review_article
  └─ review_target
```

## 2. 表分组与数据字典

### 2.1 来源与采集运行

#### `source_system`
- 作用：记录所有数据来源，包括公开 API、公开网页、官网、开源数据集、标注任务来源。
- 主键：`source_id`
- 关键字段：
  - `source_code`：来源代码，如 `bike_index`、`bikeradar`、`geobiked`
  - `source_type`：来源类型，如 `open_api`、`market_site`、`dataset`

#### `ingestion_run`
- 作用：记录某次抓取、扫描或建库运行。
- 主键：`run_id`
- 外键：
  - `source_id -> source_system.source_id`
- 关键字段：
  - `pipeline_stage`：如 `legacy_import`、`dataset_scan`
  - `started_at` / `finished_at`
  - `record_count`
  - `raw_path`

#### `source_record`
- 作用：保存原始来源中的最小记录单元，既可表示网页实体，也可表示数据集文件。
- 主键：`source_record_id`
- 外键：
  - `run_id -> ingestion_run.run_id`
- 关键字段：
  - `source_entity_type`
  - `source_entity_id`
  - `raw_payload_json`

### 2.2 开源数据集层

#### `dataset`
- 作用：记录数据集定义。
- 主键：`dataset_id`
- 外键：
  - `source_id -> source_system.source_id`
- 关键字段：
  - `dataset_code`
  - `dataset_name`
  - `homepage_url`
  - `local_path`
  - `manifest_json`

#### `dataset_version`
- 作用：记录数据集版本或当前扫描快照。
- 主键：`dataset_version_id`
- 外键：
  - `dataset_id -> dataset.dataset_id`
- 关键字段：
  - `version_tag`
  - `released_at`
  - `split_schema_json`
  - `note`

#### `dataset_annotation_record`
- 作用：保存开源数据集中的结构化标注记录。
- 当前用途：承接 GeoBIKED 的几何关键点 JSON。
- 主键：`dataset_annotation_record_id`
- 外键：
  - `dataset_version_id -> dataset_version.dataset_version_id`
  - `source_record_id -> source_record.source_record_id`
- 关键字段：
  - `sample_key`
  - `image_rel_path`
  - `annotation_type`
  - `points_json`
  - `bounding_box_json`
  - `category`
  - `source_pose`
  - `target_pose`
  - `mirror_flag`
  - `viewpoint_variation`

#### `dataset_text_description`
- 作用：保存开源数据集中的文本描述记录。
- 当前用途：承接 GeoBIKED 的 GPT-4o 描述 CSV。
- 主键：`dataset_text_description_id`
- 外键：
  - `dataset_version_id -> dataset_version.dataset_version_id`
  - `source_record_id -> source_record.source_record_id`
- 关键字段：
  - `sample_key`
  - `image_rel_path`
  - `description_source`
  - `length_label`
  - `vibe_label`
  - `style_label`
  - `description_text`

#### `dataset_feature_record`
- 作用：保存开源数据集中的结构化属性特征。
- 当前用途：
  - GeoBIKED 关键点 JSON 的元字段拆分
  - 预留 GeoBiked_parameters.csv 的参数化特征
- 主键：`dataset_feature_record_id`
- 外键：
  - `dataset_version_id -> dataset_version.dataset_version_id`
  - `source_record_id -> source_record.source_record_id`
- 关键字段：
  - `sample_key`
  - `feature_group`
  - `feature_name`
  - `feature_value_text`
  - `feature_value_num`
  - `unit_text`

### 2.3 媒体与视觉实例层

#### `media_asset`
- 作用：保存图片等媒体资源。
- 主键：`media_id`
- 外键：
  - `source_id -> source_system.source_id`
- 关键字段：
  - `original_url`
  - `local_path`
  - `sha256`
  - `width`
  - `height`

#### `image_item`
- 作用：将媒体资源注册为图像样本。
- 主键：`image_id`
- 外键：
  - `dataset_version_id -> dataset_version.dataset_version_id`
  - `media_id -> media_asset.media_id`
- 关键字段：
  - `split_name`
  - `image_role`
  - `scene_type`
  - `is_side_view`
  - `source_record_key`

#### `bicycle_instance`
- 作用：表示图像中的单辆车实例。
- 主键：`bicycle_instance_id`
- 外键：
  - `image_id -> image_item.image_id`
- 关键字段：
  - `instance_index`
  - `view_label`
  - `bbox_x / bbox_y / bbox_width / bbox_height`

### 2.4 标注任务层

#### `annotation_task`
- 作用：记录一个标注任务定义，如 `CVAT polygon`、`COCO export`
- 主键：`annotation_task_id`

#### `annotation_set`
- 作用：记录某张图像在某个任务下的一次标注版本。
- 主键：`annotation_set_id`
- 外键：
  - `annotation_task_id -> annotation_task.annotation_task_id`
  - `image_id -> image_item.image_id`

#### `annotated_object`
- 作用：保存单个标注对象。
- 主键：`annotated_object_id`
- 外键：
  - `annotation_set_id -> annotation_set.annotation_set_id`
  - `bicycle_instance_id -> bicycle_instance.bicycle_instance_id`
  - `part_taxonomy_id -> part_taxonomy.part_taxonomy_id`

#### `object_geometry`
- 作用：保存掩膜、多边形、关键点等几何数据。
- 主键：`object_geometry_id`
- 外键：
  - `annotated_object_id -> annotated_object.annotated_object_id`

### 2.5 部件与车型实体层

#### `part_taxonomy`
- 作用：统一的部件词表，是官网规格、视觉标注和热力图槽位的中心表。

#### `brand`
- 作用：品牌主表。

#### `bike_family`
- 作用：品牌下的车型家族。

#### `bike_model`
- 作用：家族下的车型定义，含年份、轮径、材质等。

#### `bike_variant`
- 作用：面向前端的整车核心实体。

#### `bike_variant_spec`
- 作用：整车规格明细表。

#### `component_catalog`
- 作用：标准化的配件目录主表。

#### `component_catalog_spec`
- 作用：配件规格明细。

#### `bike_build_component`
- 作用：整车装配桥表，连接车型和配件槽位。

#### `bike_media`
- 作用：整车三视图及其他媒体。

#### `component_media`
- 作用：配件图片及详情图。

### 2.6 报价与评测层

#### `merchant`
- 作用：销售或报价来源商家表。

#### `offer_snapshot`
- 作用：价格快照事实表，可绑定整车或配件。
- 主键：`offer_snapshot_id`
- 外键：
  - `source_id -> source_system.source_id`
  - `merchant_id -> merchant.merchant_id`
  - `component_catalog_id -> component_catalog.component_catalog_id`
  - `bike_variant_id -> bike_variant.bike_variant_id`

#### `review_article`
- 作用：评测文章事实表。

#### `review_target`
- 作用：把文章映射到品牌、整车或配件。

#### `source_entity_map`
- 作用：保存来源实体到规范实体的映射关系。

### 2.7 模型与热力图衍生层

#### `image_bike_variant_map`
- 作用：把图片中的实例映射到规范车型。

#### `bike_part_metric_snapshot`
- 作用：整车部件级热力图指标快照。

#### `component_metric_snapshot`
- 作用：配件级指标快照。

## 3. 关键关系说明

### 3.1 公开源到业务实体
- `source_system -> ingestion_run -> source_record`
- `source_record -> source_entity_map -> bike_variant / component_catalog`
- `offer_snapshot` 与 `review_article` 则保存公开网页和公开 API 的事实结果

### 3.2 开源数据集到视觉样本
- `dataset -> dataset_version -> image_item -> bicycle_instance`
- `dataset_annotation_record / dataset_text_description / dataset_feature_record` 用于保存数据集原生结构化信息
- `annotation_task / annotation_set / annotated_object / object_geometry` 用于保存项目自建标注

### 3.3 官网规格到热力图
- 官网车型进入 `bike_variant`
- 官网规格部件进入 `bike_build_component`
- 标准配件进入 `component_catalog`
- 报价与评测汇总后写入 `component_metric_snapshot` 和 `bike_part_metric_snapshot`

## 4. 当前推荐查询入口

### 4.1 看整车核心信息
- 视图：`vw_bike_core`

### 4.2 看配件核心信息
- 视图：`vw_component_core`

### 4.3 看热力图指标
- 视图：`vw_bike_part_heatmap`

### 4.4 看数据集结构化记录
- 表：
  - `dataset_annotation_record`
  - `dataset_text_description`
  - `dataset_feature_record`

## 5. 当前建库建议

- 公开源扩抓优先走 `scripts/crawl_sources_incremental.py`
- 开源数据集扩容优先补 `GeoBiked_parameters.csv` 与更多原图样本
- 前端 API 继续以统一库为唯一事实源
- 后续若增加新数据集，优先先落到 `dataset_*` 三张结构化表，再考虑映射到视觉任务层

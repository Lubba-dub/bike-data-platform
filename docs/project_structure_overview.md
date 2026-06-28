# 工程结构整理说明

## 1. 推荐理解方式

本工程可以按四条主线理解：

- `config/`：数据源与品牌官网采集配置
- `src/bike_data_platform/`：采集、转换、可视化核心实现
- `scripts/`：可直接运行的入口脚本
- `data/`：原始数据、仓库数据库、导出 API 与展示页产物

## 2. 关键目录职责

### `config/`

- `sources.yaml`：公开源、开源数据集与公开网页采集配置
- `official_sites.yaml`：品牌官网采集配置，当前已包含 `giant / merida / trek / brompton / shimano / sram / dahon / oyama / fnhon`

### `src/bike_data_platform/collectors/`

- 公开 API、静态网页、品牌官网浏览器采集器
- 图像候选采集器

### `src/bike_data_platform/transformers/`

- `warehouse.py`：基础仓库
- `brand_warehouse.py`：官网品牌仓库
- `unified_warehouse.py`：统一仓库
- `website_api.py`：前端 API 导出

### `src/bike_data_platform/visualization/`

- exploded heatmap 与模板 SVG 上色核心逻辑

### `scripts/`

- `crawl_sources_incremental.py`：按来源增量扩抓
- `crawl_brand_officials_browser.py`：浏览器自动化抓取品牌官网
- `build_brand_warehouse.py`：写入官网仓库
- `build_unified_warehouse.py`：重建统一仓库
- `export_project_data.py`：导出前端 JSON API
- `generate_template_heatmap_showcase.py`：生成当前展示页

### `data/`

- `raw/`：原始抓取与数据集下载结果
- `gold/`：SQLite 仓库与聚合导出
- `visualizations/`：最终展示页与静态可视化产物

## 3. 当前建议运行顺序

```text
公开源抓取 / 官网抓取
  -> 基础仓库 / 官网仓库
  -> 统一仓库
  -> website API 导出
  -> showcase 页面生成
```

对应命令：

```bash
python scripts/crawl_sources_incremental.py --sources bike_index bike_components bikeradar --ingest
python scripts/crawl_brand_officials_browser.py --brands merida brompton dahon fnhon oyama trek --max-products-per-brand 12 --headless
python scripts/build_brand_warehouse.py
python scripts/build_unified_warehouse.py
python scripts/export_project_data.py
python scripts/generate_template_heatmap_showcase.py
```

## 4. 已做的工程清理策略

- 展示页生成器在导出 PNG 预览后，会自动删除 `preview_*` 临时目录
- 展示页最终保留：
  - `index.html`
  - `showcase_summary.json`
  - `preview_*.png`
  - 需要保留的模板热力图 PNG

## 5. 后续建议

- 继续把 `model_year` 穿透到 unified 与前端 API
- 对 `giant` 单独做网络与地区入口排障
- 继续扩充 `trek / canyon / specialized / cannondale / bmc / pinarello`

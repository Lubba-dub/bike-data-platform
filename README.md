# bike-template-engine 与自行车数据可视化平台

本项目是一个面向《数据可视化》课程与后续研究扩展的完整工程，目标不是只做单页网页，而是打通以下全流程：

- 多源自行车与配件数据获取
- 数据清洗、标准化、建库与统一导出
- 侧视图筛选、剪影生成、标注流程组织
- 基于可复用 SVG 模板的部件热力图渲染
- 将展示页沉淀为可复用工具：`bike-template-engine`

当前工程已经从早期的 `template_heatmap_showcase` 单页演化为统一运行时体系：

- `bike-template-engine`：模板热力图运行时
- `template studio`：SVG 模板映射维护工作台
- `dataset mapper`：新数据源接入与标准协议转换工具

## 项目定位

本项目聚焦“自行车结构模板驱动的数据可视化”，核心问题是：

1. 如何从官网、公开数据集、公开 API 与评测/报价站点中获取多源数据
2. 如何把分散、噪声较高的规格文本整理成统一部件槽位
3. 如何建立适合整车、配件、报价、评测、图像与标注共存的数据仓库
4. 如何把价格、质量、性价比等指标映射到标准自行车模板
5. 如何把可视化页面进一步工具化，变成可复用的可视化引擎

## 当前成果概览

### 数据层

- 已接入公开数据集、公开 API、配件目录、评测站与品牌官网等多类来源
- 已构建 `raw -> bronze -> silver -> gold` 分层数据流
- 已建立统一仓库 `bicycle_unified_warehouse.db`
- 已导出前端可直接消费的 `website_bikes_api.json / website_parts_api.json`

### 视觉层

- 已完成公路车与山地车两套可复用 SVG 模板
- 模板通过 Inkscape 手工整理与标注，可复用于多个车型与多个指标模式
- 已支持价格、质量、性价比三种模式切换
- 已支持部件详情、模板覆盖率、品牌-部件矩阵等说明层

### 工具层

- 已实现 `bike-template-engine`
- 已实现 `template studio`
- 已实现 `dataset mapper`
- 已将旧 `template_heatmap_showcase` 入口切到统一运行时，仅作为兼容目录保留

## 推荐阅读顺序

- 工具设计文档：[bike_template_engine_design.md](docs/bike_template_engine_design.md)
- 最终实验报告论文：[final_visualization_experiment_report.md](docs/final_visualization_experiment_report.md)
- 统一数据库设计：[unified_database_design.md](docs/unified_database_design.md)
- 数据字典：[expanded_database_dictionary.md](docs/expanded_database_dictionary.md)
- SVG 热力图结构：[standard_bike_svg_heatmap_structure.md](docs/standard_bike_svg_heatmap_structure.md)

## 目录结构

```text
bike_data_platform/
  config/
    sources.yaml
    official_sites.yaml
  data/
    raw/
    bronze/
    silver/
    gold/
      exports/
    visualizations/
      bike_template_engine/
      template_heatmap_showcase/   # 兼容别名目录，底层已切换到 engine 运行时
    template_packages/
  docs/
  img_svg_templete/
  scripts/
  src/
    bike_data_platform/
      bike_template_engine/
      collectors/
      transformers/
      visualization/
```

更完整的工程结构说明见：

- [project_structure_overview.md](docs/project_structure_overview.md)

## 环境安装

在 `bike_data_platform` 目录执行：

```bash
pip install -r requirements.txt
```

如需浏览器自动化抓取：

```bash
playwright install chromium
```

## 典型运行流程

### 1. 下载公开数据集

```bash
python scripts/download_datasets.py
```

如需更完整下载：

```bash
$env:BBBICYCLES_FULL_DOWNLOAD=1
$env:GEOBIKED_GDOWN=1
python scripts/download_datasets.py
```

### 2. 采集公开网站与公开 API

```bash
python scripts/crawl_sources.py
```

增量扩抓可使用：

```bash
python scripts/crawl_sources_incremental.py
```

### 3. 使用浏览器自动化抓取品牌官网

```bash
python scripts/crawl_brand_officials_browser.py --brands shimano giant oyama merida brompton dahon fnhon trek canyon cannondale specialized --max-products-per-brand 12
```

### 4. 构建品牌仓与统一仓

```bash
python scripts/build_brand_warehouse.py
python scripts/build_unified_warehouse.py
```

### 5. 导出网站 API 数据

```bash
python scripts/export_project_data.py
```

### 6. 构建统一运行时页面

主构建脚本：

```bash
python scripts/build_bike_template_engine_suite.py
```

兼容旧入口：

```bash
python scripts/generate_template_heatmap_showcase.py
```

说明：

- `build_bike_template_engine_suite.py` 生成标准 engine 目录
- `generate_template_heatmap_showcase.py` 现已改为兼容入口，输出到旧目录，但底层运行时与 engine 一致

## 当前主要输出

### 数据仓库与导出

- 统一仓库：`data/gold/bicycle_unified_warehouse.db`
- 网站整车 API：`data/gold/exports/website_bikes_api.json`
- 网站部件 API：`data/gold/exports/website_parts_api.json`
- 网站组件 API：`data/gold/exports/website_components_api.json`
- engine 标准 payload：`data/gold/exports/bike_template_engine_payloads.json`

### 模板包

- 公路模板包目录：`data/template_packages/road/`
- 山地模板包目录：`data/template_packages/mountain/`
- 包含：
  - `package.json`
  - `mapping.json`
  - `theme.json`
  - `schema.json`
  - `template.svg`
  - `preview.svg`

### 可视化页面

- engine 主页：
  - `data/visualizations/bike_template_engine/index.html`
- template studio：
  - `data/visualizations/bike_template_engine/template_studio.html`
- dataset mapper：
  - `data/visualizations/bike_template_engine/dataset_mapper.html`

### 兼容入口

- 兼容主页：
  - `data/visualizations/template_heatmap_showcase/index.html`
- 兼容 engine 摘要：
  - `data/visualizations/template_heatmap_showcase/engine_runtime_summary.json`
- 兼容旧摘要别名：
  - `data/visualizations/template_heatmap_showcase/showcase_summary.json`

## bike-template-engine 三阶段说明

### Phase 1：bike-template-engine

职责：

- 读取模板包
- 读取标准 bike payload
- 支持价格 / 质量 / 性价比图例切换
- 渲染 SVG 模板热力图
- 输出部件详情与品牌矩阵

源码入口：

- `src/bike_data_platform/bike_template_engine/template_package.py`
- `src/bike_data_platform/bike_template_engine/dataset_mapper.py`
- `src/bike_data_platform/bike_template_engine/engine.py`

### Phase 2：template studio

职责：

- 查看 SVG 模板已绑定和未绑定的元素
- 编辑 `partKey -> svg id` 映射草案
- 实时高亮模板部件
- 导出 `mapping.json`

### Phase 3：dataset mapper

职责：

- 接入新数据源 JSON
- 提供字段映射规则
- 把外部数据映射为 engine 标准协议
- 导出标准 payload

## 手工模板设计说明

本项目的视觉核心之一，是两套可复用 SVG 模板的手工设计与标签整理：

- 公路车模板：`img_svg_templete/公路车各部件分离模板.svg`
- 山地车模板：`img_svg_templete/山地车各部分分离模板.svg`

这两套模板并非由程序自动拆分，而是通过 Inkscape 进行人工整理、命名、复核与可视化验证。这样做的原因是：

- 可以保证部件结构表达稳定
- 可以在多种车型间保持统一视觉语义
- 可以避免直接依赖原始图片轮廓造成的噪声
- 可以为价格、质量、性价比等多种模式提供统一承载层

## 文档索引

- 工具设计：[bike_template_engine_design.md](docs/bike_template_engine_design.md)
- 最终实验报告：[final_visualization_experiment_report.md](docs/final_visualization_experiment_report.md)
- 系统重构图：[system_rearchitecture_diagram.md](docs/system_rearchitecture_diagram.md)
- 可视化方案：[template_heatmap_display_schemes.md](docs/template_heatmap_display_schemes.md)
- 视觉理解研究：[vision_research_and_strategy.md](docs/vision_research_and_strategy.md)
- 标注流程：[instance_segmentation_workflow.md](docs/instance_segmentation_workflow.md)

## 注意事项

- 部分数据集体积很大，默认脚本采用保守下载策略。
- 官网抓取受网络环境、站点防护与页面结构变化影响较大。
- 当前模板页已经统一切换到 engine 运行时，但旧目录仍保留兼容别名路径。
- 统一仓中的部分山地车型仍包含推断与代表件回填；这部分在最终报告中有详细说明。
- 若继续扩展，建议优先增强：
  - Cannondale / Canyon / Trek 山地车型真实部件抓取
  - `template studio` 的模板包发布与版本管理
  - `dataset mapper` 的规则持久化与批量校验

# 标准自行车 SVG 热力图数据结构设计

## 1. 设计目标

该结构用于连接三类对象：

- 视觉识别结果
- 统一数据库中的部件与指标
- SVG / PNG / GIF / 3D 可视化渲染

## 2. 标准部件标签

当前标准显示标签采用以下 13 类：

- `tire`
- `brake`
- `chainwheel`
- `seatpost`
- `rearderailleur`
- `frame`
- `saddle`
- `fork`
- `freewhile`
- `crank`
- `handlebar`
- `shiftlever`
- `pedal`

建议内部保留一层 canonical alias：

- `freewhile -> freewheel`
- `rearderailleur -> rear_derailleur`
- `shiftlever -> shifter`
- `tire -> tyre`

这样既保留你当前训练标签，又能接数据库标准键。

## 3. 顶层结构

```json
{
  "bike_name": "C Line",
  "brand": "brompton",
  "metric_mode": "price_score",
  "views": {
    "front": null,
    "side": "https://example.com/side.jpg",
    "rear": null
  },
  "parts": []
}
```

## 4. 部件结构

```json
{
  "label": "frame",
  "display_label": "frame",
  "confidence": 0.93,
  "component_name": "Aluminium Main Frame",
  "offers_count": 3,
  "reviews_count": 8,
  "price_score": 0.72,
  "quality_score": 0.68,
  "value_score": 0.61,
  "normalized_value": 0.74,
  "fill_color": "#f2643c"
}
```

## 5. 字段说明

- `label`
  - 当前模型输出标签
- `display_label`
  - 前端展示标签，可与 `label` 保持一致
- `confidence`
  - 识别置信度
- `component_name`
  - 数据库绑定后的组件或规格名
- `offers_count`
  - 报价数量
- `reviews_count`
  - 评测或评论数量
- `price_score`
  - 价格维度指标
- `quality_score`
  - 质量维度指标
- `value_score`
  - 性价比维度指标
- `normalized_value`
  - 用于热力图上色的归一化结果
- `fill_color`
  - 渲染层最终颜色

## 6. 推荐中间对象

为了支持真实图、标准 SVG 和 exploded 视图共用，建议再加一个中间层：

```json
{
  "slot_id": "frame",
  "canonical_part_key": "frame",
  "template_shapes": ["frame_main_triangle", "rear_stay"],
  "recognition_mask_ref": "mask://frame/0",
  "component_catalog_id": 123,
  "heatmap_metrics": {
    "price_score": 0.72,
    "quality_score": 0.68,
    "value_score": 0.61
  }
}
```

## 7. 推荐渲染输出

同一份结构应支持输出：

- `photo_overlay`
- `standard_svg_heatmap`
- `exploded_heatmap`
- `animated_gif`
- `3d_scatter_html`

## 8. 当前脚本对应

已实现的导出脚本：

- `scripts/generate_exploded_heatmap_assets.py`

已实现的渲染核心：

- `src/bike_data_platform/visualization/exploded_heatmap.py`

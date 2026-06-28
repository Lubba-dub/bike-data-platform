# 从识别结果生成 Exploded Heatmap SVG/PNG 的程序方案

## 1. 输入

输入支持两种形式：

### 1.1 来自识别结果

```json
{
  "bike_name": "demo bike",
  "brand": "demo",
  "metric_mode": "price_score",
  "parts": [
    {
      "label": "frame",
      "price_score": 0.72,
      "quality_score": 0.68,
      "value_score": 0.61
    }
  ]
}
```

### 1.2 来自 `website_bikes_api.json`

程序可直接读取：

- `data/gold/exports/website_bikes_api.json`

再自动把数据库部件键映射为当前 13 个显示标签。

## 2. 核心步骤

```text
识别结果 / website API
    -> 标签标准化
    -> 选择指标维度
    -> 指标归一化
    -> 颜色映射
    -> 标准 exploded 模板渲染
    -> 输出 payload + SVG + PNG
```

## 3. 颜色映射

当前脚本采用三段色带：

- 低值：蓝色
- 中值：浅黄色
- 高值：深红色

支持的维度：

- `price_score`
- `quality_score`
- `value_score`

## 4. 当前模板策略

当前模板不是依赖真实 mask，而是：

- 使用标准侧视 exploded 布局
- 每个部件对应固定几何图元
- 同一结构可在不同维度下复用

这种方式适合：

- 报告图
- 产品原型图
- 快速热力图演示

## 5. 当前支持的 13 个部件

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

## 6. 当前输出

输出目录示例：

- `data/visualizations/exploded_heatmap_demo/exploded_heatmap_payload.json`
- `data/visualizations/exploded_heatmap_demo/exploded_heatmap.svg`
- `data/visualizations/exploded_heatmap_demo/exploded_heatmap.png`

## 7. 运行命令

### 7.1 直接从网站 API 生成

```bash
python scripts/generate_exploded_heatmap_assets.py --metric-mode price_score
```

### 7.2 指定车型

```bash
python scripts/generate_exploded_heatmap_assets.py --bike-name "C Line" --metric-mode quality_score
```

### 7.3 从自定义识别结果 JSON 生成

```bash
python scripts/generate_exploded_heatmap_assets.py --input-json path/to/recognition_result.json --metric-mode value_score
```

## 8. 后续可升级方向

- 把模板几何从固定图元升级为真正 SVG path
- 接入真实识别 mask，生成 photo overlay 和标准模板联动图
- 加入 exploded 布局自动优化
- 输出 GIF 过渡动画
- 输出 WebGL / Plotly / deck.gl 交互版

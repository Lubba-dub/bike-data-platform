# 当前数据集可视化与创新展示方案

## 1. 当前数据资产适合展示什么

基于当前统一库与导出结果，最适合先做四类展示：

- 品牌覆盖与车型规模
- 部件品类分布
- 品牌与部件矩阵
- 单车 exploded heatmap

原因：

- `price_score` 当前相对完整
- `quality_score` 与 `value_score` 仍较稀疏
- 因此现阶段更适合先突出价格层和结构层展示

## 2. 已生成的可视化资产

- `brand_bike_count.png`
- `component_part_distribution.png`
- `brand_part_matrix_heatmap.png`
- `brand_growth.gif`
- `exploded_heatmap.svg`
- `exploded_heatmap.png`

## 3. 推荐的创新展示方案

### 3.1 企业风双视图

- 左：真实整车图或剪影图
- 右：标准 exploded / SVG 热力图
- 鼠标悬停时同步高亮部件与数据卡片

适合参考：

- Apple 风格产品解释图
- 汽车官网的 exploded product storytelling
- 科技品牌的结构化对比卡

### 3.2 品牌-部件矩阵墙

- 行是品牌
- 列是部件分类
- 颜色代表覆盖数量、价格带或均值
- 点击单元格钻取到具体组件

这是最适合你现在数据库状态的“事实层总览图”。

### 3.3 Exploded Heatmap Carousel

- 每辆车一张 exploded 图
- 在不同维度之间切换：
  - `price_score`
  - `quality_score`
  - `value_score`
- 切换时做颜色过渡动画

适合做：

- PNG 序列
- GIF
- 前端轮播

### 3.4 3D Metric Space

当 `price / quality / value` 更完整后，可做：

- x：价格分数
- y：质量分数
- z：性价比分数
- 点大小：评测数
- 点颜色：报价数

推荐技术方向：

- Plotly 3D Scatter
- ECharts GL 的 `scatter3D`
- deck.gl 的 `ScatterplotLayer` / `OrthographicView`

### 3.5 品牌演化动图

- 按品牌出现顺序或数量递增动画
- 适合做 GIF 或首页 hero motion

当前已生成一个简版：

- `brand_growth.gif`

### 3.6 Exploded 3D 产品舞台

更创新的方向不是传统统计图，而是：

- 中间悬浮一辆标准侧视自行车
- 部件沿 z 轴分层拆开
- 不同部件根据价格或评分发光

更适合的技术：

- Three.js
- deck.gl 正交视图
- ECharts GL 作为快速原型

## 4. 可参考的开源方向

### 4.1 deck.gl

`deck.gl` 官方持续维护，适合大规模点云、散点、正交投影视图和交互式探索。尤其适合做品牌-部件矩阵和 3D 指标空间。  
参考：[Using deck.gl Standalone](https://github.com/visgl/deck.gl/blob/master/docs/get-started/using-standalone.md)  
参考：[Orthographic example](https://github.com/visgl/deck.gl/blob/master/examples/website/orthographic/app.tsx)

### 4.2 ECharts GL

`ECharts GL` 适合快速做 `scatter3D`、`bar3D`、`globe` 和较酷的演示稿级可视化。  
参考：[ECharts GL 概览](https://www.mintlify.com/apache/echarts/extensions/echarts-gl)  
参考：[map3D 示例](https://github.com/ecomfe/echarts-gl/blob/master/test/map3D.html)

### 4.3 Three.js

Three.js 更适合做“产品舞台式”的高级交互和 3D exploded bike 结构展示，尤其适合首页和交互 Demo。  
官方范式可优先参考 Three.js 官方 examples 体系和其社区 demo 资源。

## 5. 我对展示层的建议

### 现在就该做

- Exploded Heatmap SVG/PNG
- 品牌与部件矩阵
- 品牌覆盖 GIF
- 品类分布图

### 下一步再做

- 3D 指标空间
- 动态部件过渡动画
- Three.js 的 exploded bike showcase
- AI 风格化首页 hero 图

## 6. 为什么暂时不建议过早做 3D 指标图

当前数据中：

- `price_score` 相对完整
- `quality_score` 缺失多
- `value_score` 缺失多

所以现在就做 3D 空间会出现点太少的问题，展示层会显得不稳定。

更稳的策略是：

1. 先把价格维度和覆盖维度展示做强
2. 再补质量评价与价值分数
3. 最后上线真正高信息密度的 3D 散点与 3D 场景

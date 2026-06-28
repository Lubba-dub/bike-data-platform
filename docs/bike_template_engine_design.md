# bike-template-engine 正式设计文档

## 1. 文档目标

本文档将当前“自行车模板热力图展示页”抽象为一个可复用、可配置、可嵌入、可扩展的领域可视化工具，名称暂定为：

- `bike-template-engine`

该工具聚焦以下核心能力：

- 基于标准 SVG 模板表达不同车型
- 基于统一部件槽位表达价格 / 质量 / 性价比等多种指标
- 支持模板切换、图例切换、颜色策略切换
- 支持外部数据源接入，而不依赖单一数据库
- 支持后续演进为模板编辑器、数据映射器与插件化组件

本文档覆盖：

- 工具架构图
- 标准数据协议
- 模板包规范
- 前端 SDK 设计
- 后续插件化路线图

---

## 2. 设计定位

### 2.1 不是普通图表，而是领域模板引擎

`bike-template-engine` 不是传统 BI 中的柱状图、折线图、地图组件，而是一个“结构模板驱动的领域可视化引擎”。

它处理的对象不是抽象数轴，而是：

- 自行车结构模板
- 部件槽位语义
- 数据指标绑定
- 模板区域着色
- 数据完整度表达
- 模式切换与交互解释

### 2.2 与当前项目的关系

当前项目已经具备该工具的原型基础：

- 模板 SVG
- 模板标签映射
- `website_bikes_api.json` 导出
- 部件指标三模式切换
- 山地 / 公路模板自动切换
- 页面级交互与部件详情

因此接下来不是推倒重来，而是把现有能力整理为：

1. 可复用的数据协议
2. 可发布的模板包
3. 可嵌入的前端 SDK
4. 可维护的模板与数据映射工作台

---

## 3. 产品形态

建议将工具拆为三个连续阶段：

### 阶段一：`bike-template-engine`

定位为运行时引擎，负责：

- 读取模板包
- 读取标准化数据
- 渲染热力图
- 切换图例 / 模式 / 配色
- 输出 HTML / SVG / PNG / embed 组件

### 阶段二：`template studio`

定位为模板维护工作台，负责：

- 可视化查看 SVG 图层与标签
- 维护 `part_key -> svg_id[]` 映射
- 维护模板元信息
- 预览不同指标模式下的着色效果
- 生成模板包版本

### 阶段三：`dataset mapper`

定位为数据适配工作台，负责：

- 接入新数据源
- 将外部字段映射为标准协议
- 校验部件键与模板支持度
- 输出 engine 可消费的数据载荷

---

## 4. 工具架构图

### 4.1 总体架构

```text
                           +----------------------+
                           |   外部数据源 / DB     |
                           | official / public /  |
                           | manual / CV / API    |
                           +----------+-----------+
                                      |
                                      v
                           +----------------------+
                           |    dataset mapper    |
                           | 字段映射 / 清洗 /     |
                           | part_key 归一 / 校验  |
                           +----------+-----------+
                                      |
                                      v
                           +----------------------+
                           |   标准数据协议层      |
                           | bike payload /       |
                           | metrics / evidence   |
                           +----------+-----------+
                                      |
               +----------------------+----------------------+
               |                                             |
               v                                             v
    +--------------------------+               +--------------------------+
    |      template studio     |               |   template package repo  |
    | SVG 标签维护 / 映射维护   |-------------->| svg + mapping + theme   |
    | 模板预览 / 版本管理       |               | + schema + examples     |
    +-------------+------------+               +------------+-------------+
                  |                                             |
                  +----------------------+----------------------+
                                         |
                                         v
                           +-------------------------------+
                           |     bike-template-engine      |
                           | renderer / legend / state /   |
                           | interaction / export          |
                           +------+-------------+----------+
                                  |             |
                   +--------------+             +------------------+
                   |                                             |
                   v                                             v
        +------------------------+                   +------------------------+
        | Web / React / HTML SDK |                   | Plugin / Embed Output  |
        | 单页 / 报告 / 工作台    |                   | iframe / npm / BI扩展  |
        +------------------------+                   +------------------------+
```

### 4.2 运行时分层

```text
Data Layer
  -> 标准 bike payload
Template Layer
  -> svg / mapping / legend / theme
Render Layer
  -> 颜色映射 / missing strategy / evidence encoding
Interaction Layer
  -> hover / click / tooltip / mode switch / compare
Delivery Layer
  -> html page / react component / iframe / png
```

---

## 5. 核心设计原则

### 5.1 模板优先

同一车型的可视化表达必须基于稳定模板，而不是直接依赖原始图片像素区域。

### 5.2 数据诚实

对“未映射”“数据不足”“指标缺失”要区分表达，不伪造部件区域。

### 5.3 协议先行

数据源、模板、渲染器之间通过标准协议解耦，避免页面代码直接依赖单一导出脚本。

### 5.4 组件化交付

所有能力最终应沉淀为：

- 一份模板包规范
- 一份标准数据协议
- 一套可嵌入 SDK

### 5.5 多模式复用

同一辆车同一模板，必须支持：

- 价格图例
- 质量图例
- 性价比图例
- 数据完整度辅助层
- 后续升级建议模式

---

## 6. 标准数据协议

### 6.1 设计目标

标准数据协议用于解耦：

- 数据源结构
- 模板结构
- 前端渲染逻辑

引擎只认协议，不认具体数据库表结构。

### 6.2 顶层对象

```json
{
  "schemaVersion": "1.0.0",
  "bikeId": "merida-one-sixty-500",
  "bikeName": "ONE-SIXTY 500",
  "brand": "merida",
  "bikeType": "mountain",
  "templateType": "mountain",
  "views": {
    "front": null,
    "side": "https://example.com/one-sixty-side.jpg",
    "rear": null
  },
  "availableModes": [
    "price_score",
    "quality_score",
    "value_score"
  ],
  "defaultMode": "price_score",
  "parts": [],
  "summary": {},
  "meta": {}
}
```

### 6.3 部件对象

```json
{
  "partKey": "shock",
  "displayName": "Shock",
  "templateLabels": ["shock"],
  "componentName": "RockShox Super Deluxe Ultimate",
  "brandHint": "RockShox",
  "sourceType": "observed",
  "evidence": {
    "offersCount": 2,
    "reviewsCount": 5,
    "confidence": 0.92,
    "coverage": "high"
  },
  "metrics": {
    "price_score": 245.31,
    "quality_score": 0.86,
    "value_score": 0.29
  },
  "render": {
    "status": "mapped",
    "fillValue": 0.74,
    "fillColor": "#f05a3f",
    "strokeOpacity": 0.88
  }
}
```

### 6.4 字段定义

#### 顶层字段

- `schemaVersion`
  - 协议版本
- `bikeId`
  - 车型唯一标识
- `bikeName`
  - 车型展示名
- `brand`
  - 品牌名
- `bikeType`
  - 业务类型，如 `road / mountain / folding`
- `templateType`
  - 实际使用的模板类型
- `views`
  - 三视图或侧视图资源
- `availableModes`
  - 当前数据支持的图例模式
- `defaultMode`
  - 默认模式
- `parts`
  - 标准部件数组
- `summary`
  - 聚合统计
- `meta`
  - 额外元信息

#### 部件字段

- `partKey`
  - 标准部件键
- `displayName`
  - 前端展示名
- `templateLabels`
  - 映射到模板中的标签集合
- `componentName`
  - 部件名或规格名
- `brandHint`
  - 组件品牌提示
- `sourceType`
  - `observed / inferred / representative / missing`
- `evidence`
  - 证据强度对象
- `metrics`
  - 多模式指标对象
- `render`
  - 渲染层派生结果

### 6.5 `sourceType` 枚举

- `observed`
  - 真实车型部件记录
- `inferred`
  - 基于当前车其他信息推断
- `representative`
  - 基于组件库代表项回填
- `missing`
  - 无法绑定有效数据

### 6.6 `render.status` 枚举

- `mapped`
  - 已映射到模板并可着色
- `template_missing`
  - 数据存在但模板未拆出该区域
- `unmapped`
  - 数据协议存在但未找到模板标签
- `empty`
  - 数据缺失

### 6.7 顶层 `summary` 示例

```json
{
  "partsCount": 13,
  "mappedPartsCount": 12,
  "templateCoverage": 0.92,
  "evidenceScore": 0.78,
  "hasPhoto": true,
  "hasSilhouette": true
}
```

### 6.8 模式配置对象

推荐在 payload 或模板配置中保留模式元数据：

```json
{
  "modes": {
    "price_score": {
      "label": "价格",
      "legendTitle": "价格热力图",
      "palette": "warm"
    },
    "quality_score": {
      "label": "质量",
      "legendTitle": "质量热力图",
      "palette": "cool"
    },
    "value_score": {
      "label": "性价比",
      "legendTitle": "性价比热力图",
      "palette": "teal"
    }
  }
}
```

---

## 7. 模板包规范

### 7.1 目标

模板包是可发布、可版本化、可复用的视觉资产单元。

每个模板包应能独立回答四个问题：

1. 长什么样
2. 哪些图层对应哪些部件
3. 支持哪些模式与图例
4. 如何被前端加载

### 7.2 建议目录结构

```text
mountain-template/
  package.json
  template.svg
  preview.png
  mapping.json
  theme.json
  schema.json
  example-bike.json
  CHANGELOG.md
```

### 7.3 `package.json`

```json
{
  "name": "@bike-templates/mountain-template",
  "version": "1.0.0",
  "templateType": "mountain",
  "title": "Mountain Bike Template",
  "engineVersion": ">=1.0.0",
  "supportedParts": [
    "frame",
    "fork",
    "brake",
    "seatpost",
    "shock",
    "saddle",
    "handlebar",
    "shiftlever",
    "rearderailleur",
    "freewhile",
    "chainwheel",
    "pedal",
    "tyre"
  ]
}
```

### 7.4 `mapping.json`

```json
{
  "frame": [
    "frame_top_tube",
    "frame_down_tube",
    "frame_seat_stay",
    "frame_chain_stay"
  ],
  "fork": ["fork"],
  "shock": ["Shock_Absorber", "rear_shock_absorber"],
  "brake": ["brake", "front_brake", "brake_lever_left", "brake_lever_right"],
  "seatpost": ["seatpost"],
  "tyre": ["front_tire", "back_tire", "back_tire_0", "back_tire_1"],
  "rearderailleur": ["rearderailleur"]
}
```

### 7.5 `theme.json`

```json
{
  "palettes": {
    "warm": ["#fff6ef", "#f7b37a", "#e85b3a", "#991f17"],
    "cool": ["#eef6ff", "#8eb7ff", "#3d6ef7", "#15308a"],
    "teal": ["#effcf8", "#8be0cb", "#22b8a2", "#0d6b66"]
  },
  "missing": {
    "fill": "#d9dde3",
    "stroke": "#a0a7b4",
    "opacity": 0.45
  },
  "legend": {
    "position": "bottom-right",
    "showEvidenceLayer": true
  }
}
```

### 7.6 `schema.json`

用于声明模板支持的最小字段要求：

```json
{
  "requiredParts": ["frame", "fork", "tyre"],
  "optionalParts": [
    "shock",
    "seatpost",
    "brake",
    "saddle",
    "handlebar",
    "shiftlever",
    "rearderailleur",
    "freewhile",
    "chainwheel",
    "pedal"
  ],
  "requiredModes": ["price_score"],
  "optionalModes": ["quality_score", "value_score"]
}
```

### 7.7 模板包版本规则

建议采用语义化版本：

- `major`
  - 模板映射结构变更
- `minor`
  - 新增部件或新增可选模式
- `patch`
  - 修复标签、图例、主题细节

---

## 8. 前端 SDK 设计

### 8.1 设计目标

前端 SDK 负责把“模板包 + 标准数据协议”渲染成可交互热力图组件。

它应同时支持：

- 原生 HTML 页面
- React 页面
- 报告嵌入
- 后续插件化容器

### 8.2 SDK 包拆分

建议拆为三个包：

```text
@bike-template-engine/core
@bike-template-engine/react
@bike-template-engine/devtools
```

#### `core`

负责：

- 读取模板包
- 读取标准协议
- 计算颜色
- 计算图例
- 生成渲染状态

#### `react`

负责：

- React 组件封装
- 状态联动
- UI 面板

#### `devtools`

负责：

- 模板调试
- 标签检查
- 数据覆盖检查

### 8.3 核心 API 设计

#### 初始化

```ts
import { createBikeTemplateEngine } from "@bike-template-engine/core";

const engine = createBikeTemplateEngine({
  templatePackage,
  bikePayload,
  mode: "price_score"
});
```

#### 渲染到容器

```ts
engine.mount(document.getElementById("app"));
```

#### 切换模式

```ts
engine.setMode("quality_score");
```

#### 切换模板

```ts
engine.setTemplate(roadTemplatePackage);
```

#### 更新数据

```ts
engine.setData(nextBikePayload);
```

#### 导出

```ts
await engine.exportSVG();
await engine.exportPNG();
```

### 8.4 React 组件 API

```tsx
<BikeTemplateHeatmap
  template={mountainTemplate}
  data={bikePayload}
  mode="price_score"
  legend
  detailPanel
  comparePanel
  onPartClick={handlePartClick}
/>
```

### 8.5 关键 Props

- `template`
  - 模板包对象
- `data`
  - 标准协议数据
- `mode`
  - 当前指标模式
- `legend`
  - 是否显示图例
- `detailPanel`
  - 是否显示部件详情
- `comparePanel`
  - 是否显示模板对照或多车对照
- `missingStrategy`
  - 缺失值表达策略
- `themeOverride`
  - 局部主题覆盖

### 8.6 UI 状态模型

```ts
type EngineState = {
  bikeId: string;
  templateType: string;
  mode: "price_score" | "quality_score" | "value_score";
  selectedPartKey: string | null;
  hoveredPartKey: string | null;
  legendOpen: boolean;
  compareTemplateType: string | null;
};
```

### 8.7 图例切换能力

为符合你的项目重点，SDK 必须内置“图例系统”。

建议支持：

- 模式切换图例
  - `price / quality / value`
- 配色切换图例
  - `classic / warm / cool / teal / mono`
- 证据层开关
  - 是否显示描边强度
- 缺失策略图例
  - 灰色代表什么

### 8.8 交互能力

最小交互集建议为：

- hover 高亮
- click 锁定部件
- tooltip
- 模式切换动画
- 模板切换
- 多车切换
- 导出当前视图

### 8.9 导出能力

建议内置：

- `exportSVG()`
- `exportPNG()`
- `exportState()`
- `exportEmbedConfig()`

---

## 9. bike-template-engine 运行流程

### 9.1 基本流程

```text
加载模板包
  -> 校验模板版本
  -> 读取 SVG 与 mapping
加载 bike payload
  -> 校验协议字段
  -> 校验部件键
  -> 计算模板覆盖率
选择 mode
  -> 读取指标
  -> 归一化
  -> 计算颜色与证据层
渲染页面
  -> SVG path 着色
  -> 图例更新
  -> 详情区更新
```

### 9.2 缺失值表达策略

建议引擎内建统一策略：

- `mapped + 有值`
  - 正常着色
- `mapped + 无值`
  - 浅灰 + tooltip 标注“已映射但指标不足”
- `template_missing`
  - 列表中展示，模板不伪造区域
- `unmapped`
  - 进入开发警告层

---

## 10. template studio 设计

### 10.1 目标

`template studio` 用于可视化维护模板，而不是手工反复改 SVG id 与代码字典。

### 10.2 核心页面

#### 页面 A：SVG 图层检查器

- 显示原始 SVG
- 点击 path 查看 id
- 查看 path 分组
- 搜索标签

#### 页面 B：部件映射面板

- 左侧标准 `partKey` 列表
- 右侧已绑定 svg ids
- 支持拖拽或点击绑定
- 显示是否冲突、是否遗漏

#### 页面 C：实时热力图预览

- 选择模板
- 选择样例数据
- 切换 `price / quality / value`
- 实时查看着色结果

#### 页面 D：模板发布页

- 查看模板版本
- 校验通过项
- 生成模板包

### 10.3 Studio 的输入输出

输入：

- `template.svg`
- 标准 `partKey` 字典
- 样例 bike payload

输出：

- `mapping.json`
- `theme.json`
- `package.json`
- 模板预览图

### 10.4 Studio 校验规则

- 一个 svg id 不应被多个关键部件重复绑定
- `requiredParts` 不应为空
- 模板至少要有 `frame / fork / tyre`
- 模板预览必须通过最小覆盖率校验

---

## 11. dataset mapper 设计

### 11.1 目标

`dataset mapper` 解决“新数据源如何进入模板引擎”的问题。

它把外部数据转为标准协议，而不是让每个页面都自己写映射逻辑。

### 11.2 支持的数据源类型

- 当前数据库导出 JSON
- 官方网站抓取结果
- 公开数据集结构化结果
- 手工录入 CSV / Excel
- 未来 CV 识别结果

### 11.3 Mapper 处理步骤

```text
读取数据源
  -> 字段识别
  -> part_key 归一
  -> 指标字段映射
  -> 品牌与车型归一
  -> 证据字段归一
  -> 模板支持度检查
  -> 输出标准 payload
```

### 11.4 Mapper 规则对象

```json
{
  "sourceName": "website_bikes_api",
  "bikeIdField": "bike_id",
  "bikeNameField": "bike_name",
  "bikeTypeField": "bike_type",
  "partsPath": "parts",
  "partMappings": {
    "tyre": "tyre",
    "wheel": "tyre",
    "rearshockabsorber": "shock",
    "seat post": "seatpost"
  },
  "metricMappings": {
    "price_score": "price_score",
    "quality_score": "quality_score",
    "value_score": "value_score"
  }
}
```

### 11.5 Mapper 输出等级

- `strict`
  - 不满足协议直接报错
- `compatible`
  - 可做别名兼容
- `best_effort`
  - 缺字段时保守回填

### 11.6 Mapper 的价值

它让未来接入：

- 新品牌官网
- 课程演示数据
- 第三方 API
- 识别模型输出

都不需要重写前端渲染逻辑。

---

## 12. 插件化路线图

### 12.1 目标

长期目标不是只服务本项目页面，而是将其发布为可复用可嵌入的视觉组件。

### 12.2 路线分层

#### 路线 A：项目内模块化

输出：

- `src/bike_template_engine/`
- 内部复用 API

适合先完成当前工程内解耦。

#### 路线 B：npm SDK

输出：

- `@bike-template-engine/core`
- `@bike-template-engine/react`

适合多个前端项目复用。

#### 路线 C：iframe/embed 组件

输出：

- 独立 URL
- 通过 query 或 json config 加载

适合报告、静态站、低代码系统嵌入。

#### 路线 D：BI 插件

输出：

- Power BI 自定义 visual
- FineReport/FineBI 自定义扩展图表

适合企业级大屏和数据分析平台集成。

### 12.3 分阶段规划

#### Phase 1：当前项目整理成 `bike-template-engine`

目标：

- 把当前散落在脚本和页面中的模板逻辑抽离
- 建立标准协议与模板包
- 页面通过 engine 渲染

交付：

- engine core
- 第一版模板包
- 当前 showcase 页面接入 engine

#### Phase 2：补 `template studio`

目标：

- 可视化维护 SVG 标签映射
- 降低新增模板和修模板成本

交付：

- SVG layer inspector
- mapping editor
- preview panel
- package exporter

#### Phase 3：补 `dataset mapper`

目标：

- 让新数据源也能快速套模板

交付：

- 映射规则编辑器
- partKey 归一规则
- 协议导出器
- 数据覆盖率检查器

#### Phase 4：发布 SDK

目标：

- 把当前工具沉淀为前端组件能力

交付：

- core npm package
- react package
- demo site

#### Phase 5：插件化探索

目标：

- 进入 BI / 报表工具生态

交付：

- Power BI custom visual 原型
- iframe embed 版本
- 后续企业内集成适配

---

## 13. 当前项目到 engine 的整理建议

### 13.1 建议目录

```text
src/
  bike_template_engine/
    core/
      engine.py
      protocol.py
      template_loader.py
      render_state.py
    templates/
      road/
      mountain/
    adapters/
      website_api_adapter.py
    export/
      svg_export.py
      png_export.py
```

前端建议：

```text
web/
  bike-template-engine/
    core/
    react/
    studio/
    mapper/
```

### 13.2 当前代码迁移来源

建议重点吸收以下现有能力：

- 模板映射与模式切换逻辑
  - `scripts/generate_template_heatmap_showcase.py`
- 模板标签标准化与渲染
  - `src/bike_data_platform/visualization/exploded_heatmap.py`
- 数据清洗与部件协议输出
  - `src/bike_data_platform/transformers/website_api.py`

### 13.3 第一版 engine 最小功能

- 加载 road / mountain 模板
- 加载标准 bike payload
- 三模式切换
- 图例切换
- 缺失值诚实表达
- 详情卡联动
- 导出 HTML/SVG/PNG

---

## 14. 里程碑建议

### M1：协议冻结

- 冻结 `bike payload` 协议
- 冻结 `template package` 目录规范

### M2：engine 跑通

- 当前 showcase 页面改为 engine 驱动

### M3：studio 跑通

- 能在图形界面里改 mountain / road 模板映射

### M4：mapper 跑通

- 新增一份外部 JSON，在不改前端代码前提下完成接入

### M5：对外复用

- 以 npm / iframe 形式完成首个外部嵌入示例

---

## 15. 风险与约束

### 15.1 模板不是无限精细

某些部件如 `crank / chainwheel / freewhile` 仍可能受限于 SVG 模板精度。

应对策略：

- 保持 `template_missing` 状态
- 在 studio 中持续补模板

### 15.2 数据源质量不稳定

不同品牌、不同官网、不同来源会造成部件信息稀疏。

应对策略：

- mapper 负责协议兼容
- engine 负责诚实表达

### 15.3 不应把引擎与单库强绑定

否则工具无法复用。

应对策略：

- 统一通过标准 payload 输入

---

## 16. 结论

`bike-template-engine` 的本质，是把当前“自行车模板热力图页面”升级为一个可复用的领域可视化工具。

它的核心不是再做一个页面，而是沉淀出三种长期资产：

- 标准数据协议
- 模板包规范
- 可嵌入渲染引擎

在此基础上：

- `template studio` 解决模板维护问题
- `dataset mapper` 解决新数据接入问题
- SDK 与插件化路线解决复用与分发问题

这条路线能够让当前课程项目继续向：

- 研究型可解释可视化系统
- 面向多车型的模板热力图库
- 可嵌入式 BI 视觉组件

持续演进。

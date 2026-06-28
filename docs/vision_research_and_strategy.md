# 自行车视觉理解方向调研与实施建议

## 1. 你的目标到底是什么

你现在的目标不是单纯“识别图片里有没有自行车”，而是四件事同时成立：

- 识别这是一辆自行车
- 理解这辆车的结构和主要部件
- 生成可以点击、可以上色的区域
- 最后把视觉区域和数据库里的标准部件、报价、评分对齐

这意味着最合适的路线不是只用单一模型，而是分层处理：

- 几何与主体层
- 部件检测/分割层
- 标准部件槽位映射层
- 数据库绑定层

## 2. 当前值得关注的开源方向

### 2.1 SAM 2

- `SAM 2` 是 Meta 的可提示分割模型，支持图像和视频场景，适合作为高质量掩膜生成和交互式修正底座。  
  参考：[facebookresearch/sam2](https://github.com/facebookresearch/sam2)

### 2.2 Grounding DINO

- `Grounding DINO` 是开放词汇检测模型，可以用文本提示定位任意对象，适合用文字提示找 `bicycle`、`wheel`、`saddle`、`handlebar`、`fork` 等目标。  
  参考：[Grounding DINO](https://github.com/open-mmlab/mmdetection/blob/main/configs/grounding_dino/README.md)

### 2.3 Grounded SAM / Grounded SAM 2

- `Grounded SAM` 把 Grounding DINO 和 SAM 组合，用“文本找目标 + 掩膜抠区域”的方式实现开放词汇分割。  
  参考：[Grounded-Segment-Anything](https://github.com/IDEA-Research/Grounded-Segment-Anything/blob/main/README.md)
- `Grounded SAM 2` 进一步升级到 `SAM 2`，适合更高质量 mask 和未来视频跟踪。  
  参考：[Grounded-SAM-2](https://github.com/IDEA-Research/Grounded-SAM-2)

### 2.4 Ultralytics YOLO 分割

- `Ultralytics` 当前继续支持实例分割训练和部署，适合你在自己的 8 类或 12 类部件数据上做一个可部署、可控的专用模型。  
  参考：[Instance segmentation task](https://github.com/ultralytics/ultralytics/blob/main/docs/en/tasks/segment.md)
- 新版文档也继续强调实例分割与跟踪工作流。  
  参考：[Instance segmentation and tracking](https://github.com/ultralytics/ultralytics/blob/main/docs/en/guides/instance-segmentation-and-tracking.md)

### 2.5 BIKED

- `BIKED` 不是传统检测项目，但它非常贴近你的方向，因为它提供标准化自行车设计数据、部件分解图和语义 mask，适合做“标准侧视模板”和“结构先验”。  
  参考：[BIKED](https://decode.mit.edu/projects/biked/)

## 3. 对你最有用的不是“找一个万能模型”

### 3.1 为什么单模型不够

- `YOLO-seg` 部署快，但小部件边界容易粗
- `SAM 2` 掩膜强，但默认不理解“哪个区域对应数据库里的哪个标准部件”
- `Grounding DINO` 会告诉你“哪里像车轮/座垫”，但输出主要是框，不是最终精细可点击区域

所以你的系统更适合：

1. 用开放词汇模型做粗定位
2. 用分割模型做精区域
3. 用标准部件词表和模板做结构约束
4. 用数据库实体做最终绑定

## 4. 最适合你的视觉架构

## 4.1 第一层：主体提取

目标：

- 先把整车从背景里干净拿出来
- 快速生成前端可展示剪影

当前项目已新增：

- [generate_white_background_silhouettes.py](file:///e:/cocoon/study/%E5%A4%8D%E4%B9%A0%E8%B5%84%E6%96%99/%E6%95%B0%E6%8D%AE%E5%8F%AF%E8%A7%86%E5%8C%96/bike_data_platform/scripts/generate_white_background_silhouettes.py)

这一步适合：

- 官网白底商品图
- 纯背景整车图
- 做热力图原型底图

## 4.2 第二层：大部件实例分割

建议先做 8 类：

- `frame`
- `front_wheel`
- `rear_wheel`
- `fork`
- `handlebar`
- `saddle`
- `drivetrain`
- `brake`

原因：

- 这些部件决定前端点击体验
- 类间边界相对稳定
- 小数据更容易学出来

## 4.3 第三层：结构先验

把视觉结果约束到标准槽位：

- `part_taxonomy`
- `bike_build_component`
- `component_catalog`

也就是说，视觉模型输出的不是随意文本，而是尽量落到：

- `wheel`
- `fork`
- `handlebar`
- `drivetrain`

这层约束能显著降低后续“视觉识别出来了，但没法对数据库上色”的问题。

## 4.4 第四层：数据库绑定

最终前端要点的是：

- 标准部件槽位
- 该槽位对应的标准商品
- 该商品的价格、评分、性价比

因此视觉层输出应尽量绑定：

- `part_taxonomy_id`
- `component_catalog_id`
- `bike_variant_id`

## 5. 我建议你的实际路线

### 路线 A：先做能跑的项目原型

- 白底图先用启发式剪影
- 侧视图先用 `YOLO-seg` 做 8 类部件分割
- 热力图先上 `frame / wheel / fork / handlebar / saddle / drivetrain / brake`
- 小部件先不追求极致

### 路线 B：中期提升精度

- 用 `Grounding DINO + SAM 2` 生成初掩膜
- 人工在 `CVAT` 里修正
- 继续回灌训练 `YOLO-seg`

### 路线 C：后期做强交互

- 引入标准化自行车 SVG 模板
- 用关键点和模板做几何对齐
- 把视觉结果从“像哪个部件”升级成“落在标准模板哪一槽位”

## 6. 如果你问“有没有直接识别自行车部件的成熟开源项目”

结论是：

- 有大量“自行车检测”项目，但大多只做 `bicycle / e-bike` 检测
- 真正针对“整车部件实例分割”的成熟通用开源项目并不多
- 对你最有价值的不是直接找现成成品，而是组合：
  - `DelftBikes`
  - `GeoBIKED`
  - `BIKED`
  - `SAM 2 / Grounded SAM 2`
  - 自己的小规模高质量掩膜集

## 7. 视觉理解应该怎么处理

可以把它理解成四个问题：

### 7.1 看见什么

- 是否存在完整整车
- 是否接近侧视图
- 是否适合进入热力图流程

对应你当前项目：

- 图片采集
- 侧视初筛
- 白底剪影

### 7.2 分出什么

- 哪些像轮组、车架、前叉、把组、座垫
- 哪些区域可以点击

对应：

- 实例分割
- 掩膜导出

### 7.3 结构上属于什么

- 这个区域不是随便一个 patch，而是 `rear_wheel` 或 `drivetrain`
- 这个区域要落在标准槽位里，而不是自由文本类别

对应：

- `part_taxonomy`
- 模板或关键点约束

### 7.4 商业上对应什么

- 这辆车可能是哪个 `bike_variant`
- 这个槽位可能对应哪个 `component_catalog`
- 它该显示什么价格、评分和性价比

对应：

- 统一数据库
- 规范实体映射

## 8. 我对你项目的最终建议

- 前端原型期：优先“整车剪影 + 大部件热力图”
- 训练策略：先 8 类，后细化
- 标注策略：用 `SAM 2 / Grounded SAM 2` 做初掩膜，人工修正
- 结构策略：坚持 `part_taxonomy -> component_catalog -> heatmap_metrics`
- 数据策略：继续扩公开源，但实体扩容优先补“别名、映射、标准槽位”

## 9. 对当前工程最适合的下一步

- 继续增量扩抓公开源，优先扩 `bike_components` 与 `bikeradar`
- 在统一数据库里继续强化 `alias / source_entity_map / taxonomy` 三层
- 先用当前新增剪影脚本处理白底图，快速生成前端底图
- 后续如果你愿意，我可以继续给你接：
  - `Grounding DINO + SAM2` 的自动初掩膜脚本
  - 白底剪影结果写入统一数据库
  - 一个“视觉识别结果 -> part_taxonomy -> website_api”的完整链路

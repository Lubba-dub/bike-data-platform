# 自行车部件实例分割数据构建工作流

## 1. 你现在最应该怎么做

如果你的目标是“用户上传一张自行车侧面图，系统能精确点击并给部件区域染色”，最现实的路线不是一开始就做 15 类以上细粒度分割，而是采用两阶段方案：

### 阶段 A：先做可用的 8 类分割

- `frame`
- `front_wheel`
- `rear_wheel`
- `fork`
- `handlebar`
- `saddle`
- `drivetrain`
- `brake`

这样做的好处是：

- 标注速度快
- 类间边界更稳定
- 小样本更容易学出来
- 更适合先搭网站原型

### 阶段 B：再细化为 12 到 15 类

等第一版模型稳定后，再把 `drivetrain` 拆成：

- `crankset`
- `chain`
- `cassette`
- `rear_derailleur`
- `front_derailleur`

并把 `brake` 拆成：

- `brake_front`
- `brake_rear`

## 2. 图片应该怎么获取

当前工程已经提供图片采集脚本：

```bash
python scripts/collect_bike_images.py --source all --limit 200 --download
```

默认会从以下来源采集候选图：

- `Bike Index API`：真实世界整车照片
- `Wikimedia Commons`：公开授权图片候选

输出：

- 候选清单：`data/annotations/manifests/bike_image_candidates.json`
- 候选表格：`data/annotations/manifests/bike_image_candidates.csv`
- 实际下载图片：`data/raw/images/`

## 3. 哪些图片适合做实例分割标注

优先保留以下图像：

- 整车基本完整入镜
- 接近正侧视图
- 背景不要太乱
- 轮组、车架、把组、座垫基本可见
- 遮挡不严重

建议剔除：

- 俯视、斜前方、斜后方角度太大的图片
- 只拍局部的图片
- 多辆车重叠严重的图片
- 分辨率过低、模糊严重的图片

## 4. 用什么工具标注掩膜

最推荐：

- `CVAT`

原因：

- 对多边形和实例分割支持成熟
- 导出 `COCO instance segmentation` 很方便
- 适合多人协作和审校

也可选：

- `Label Studio`

但如果你后续要直接训练检测/分割模型，`CVAT -> COCO` 的路径通常更顺。

## 5. 在 CVAT 里怎么标注

### 创建任务

1. 新建任务
2. 上传筛选后的整车图片
3. 标签建议先用 8 类
4. 标注类型选择 `Polygon`

### 标签建议

第一阶段标签：

- `frame`
- `front_wheel`
- `rear_wheel`
- `fork`
- `handlebar`
- `saddle`
- `drivetrain`
- `brake`

### 标注原则

- 沿可见轮廓描边，不要把背景卷进去
- 被遮挡部分不要凭空补全
- 只标可见区域
- 左右两个轮子必须分开标
- 小部件边界不清时宁可并入大类，不要乱拆

### 标注粒度建议

- `frame`：只标车架主体，不含前叉、轮组
- `fork`：前叉单独标
- `handlebar`：把横、把立可合并
- `drivetrain`：牙盘、链条、飞轮、后拨早期合并
- `brake`：前后刹车系统先粗合并，后续再细化

## 6. 每张图需要标多少东西

不要追求“能标的都标”，建议按以下优先级：

### 必标

- `frame`
- `front_wheel`
- `rear_wheel`
- `fork`
- `handlebar`
- `saddle`

### 条件允许再标

- `drivetrain`
- `brake`

如果链条、后拨太小或被遮挡，可以暂时不标，先保证主结构质量。

## 7. 需要多少张图

建议的数据规模：

- 原型期：`150 - 300` 张高质量掩膜图
- 第一版可用模型：`400 - 800` 张
- 想要更稳：`1000+` 张

如果是自己小规模做项目，推荐：

- 先采集 `300` 张候选图
- 精筛后留 `180 - 250` 张
- 先精标这批图

## 8. 标完以后怎么导出

在 `CVAT` 中导出：

- `COCO 1.0`

最好选择带实例分割多边形信息的导出格式。

导出后你会得到：

- `images/`
- `annotations/instances_default.json`

## 9. 如何转换成 YOLOv8-seg 数据集

工程里已经提供转换脚本：

```bash
python scripts/convert_coco_to_yolo_seg.py ^
  --coco data/annotations/exports/instances_default.json ^
  --images data/raw/images ^
  --output data/annotations/yolo_seg ^
  --classes frame front_wheel rear_wheel fork handlebar saddle drivetrain brake
```

转换后会生成：

- `data/annotations/yolo_seg/images/train`
- `data/annotations/yolo_seg/images/val`
- `data/annotations/yolo_seg/labels/train`
- `data/annotations/yolo_seg/labels/val`
- `data/annotations/yolo_seg/data.yaml`

## 10. 如何训练分割模型

推荐起步模型：

- `YOLOv8n-seg`
- `YOLOv8s-seg`

训练示例：

```bash
yolo task=segment mode=train model=yolov8n-seg.pt data=data/annotations/yolo_seg/data.yaml epochs=100 imgsz=960 batch=8
```

如果显存更大，可换：

```bash
yolo task=segment mode=train model=yolov8s-seg.pt data=data/annotations/yolo_seg/data.yaml epochs=100 imgsz=1024 batch=8
```

## 11. 如何把公开数据集和自建掩膜结合

建议这样组合：

### `DelftBikes`

用途：

- 学部件类别
- 学部件大致位置先验
- 可先做检测或弱监督分割辅助

局限：

- 主要是框标注，不是高质量实例掩膜

### `GeoBIKED`

用途：

- 提供结构先验
- 很适合辅助你理解“标准侧视图”几何布局

局限：

- 不是现成的部件掩膜集

### 你自己标的小规模高质量掩膜集

用途：

- 真正决定网站里“点击精度”和“上色边界”

结论：

- `公开数据集负责扩大认知范围`
- `自建掩膜集负责提升边界精度`

## 12. 一个实用的最小可行工作流

建议直接按下面做：

1. 用 `collect_bike_images.py` 拉 `200 - 300` 张整车候选图
2. 人工筛到 `180` 张左右侧视图
3. 用 `build_annotation_manifest.py` 生成标注清单
4. 在 `CVAT` 里只标 8 类
5. 导出 `COCO instance segmentation`
6. 用 `convert_coco_to_yolo_seg.py` 转为 YOLO-seg
7. 训练 `YOLOv8n-seg`
8. 先看车架、轮组、前叉、把组、座垫的效果
9. 再决定是否把传动和刹车细分

## 13. 额外建议

- 早期不要一开始追求链条、前拨这类超小目标的高精度
- 网站先做到“大部件可点、颜色覆盖正确”就已经很强
- 如果后面想进一步提升边界，可考虑：
- 增加纯侧视图比例
- 对轮组、车架、前叉做更多高质量掩膜
- 用 `SAM2` 或 `Grounded-SAM` 生成初掩膜，再人工修正

## 14. 你下一步最该做什么

如果你现在马上要开始，最推荐执行这 3 条命令：

```bash
python scripts/collect_bike_images.py --source all --limit 250 --download
python scripts/build_annotation_manifest.py
```

然后把筛选后的图片导入 `CVAT` 开始标 8 类掩膜。

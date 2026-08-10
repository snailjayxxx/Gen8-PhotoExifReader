# Gen8 Photo EXIF Reader — v0.1 设计

## 目标

在 Synology NAS 上以**只读方式**扫描用户现有摄影目录，不移动、不重命名、不修改 RAW/JPEG/XMP。系统建立独立 SQLite 索引，用于统计摄影主题、器材与 EXIF 分布，并逐步提供照片反查和筛选。

## 用户现有目录模型

系统不要求统一历史目录结构。典型情况包括：

```text
照片库/
├── 旅游/                       # 顶层目录 = 摄影主题
│   ├── 2021北海道/
│   │   ├── RAW/
│   │   │   ├── DSC00001.ARW
│   │   │   └── 修图/DSC00001.jpg
│   │   └── jpg/DSC00001.JPG
│   ├── 2024名古屋/
│   │   ├── 名古屋/DSC01001.ARW
│   │   └── jpg/DSC01001.JPG
│   └── 2026名古屋/
│       ├── 名古屋RAW/
│       │   ├── DSC02001.ARW
│       │   └── 修图/DSC02001-Edit.jpg
│       └── jpg/DSC02001.JPG
├── 散步/
├── 拍娃/
└── 拍猫/
```

### 主题

照片库根目录下的第一级目录自动作为 `theme`，例如 `旅游 / 散步 / 拍娃 / 拍猫`。

### 文件角色

文件被归类为：

- `raw`：ARW/CR3/NEF/RAF/DNG 等 RAW 扩展名。
- `camera_jpeg`：位于 `jpg/jpeg/直出` 等目录中的 JPEG/HEIF/TIFF。
- `edited`：路径中出现 `修图/成片/导出/edited/Lightroom/LR` 等关键词。
- `jpeg`：其它普通 JPEG/HEIF/TIFF。

目录关键字使用“包含匹配”，因此 `2026RAW`、`名古屋RAW` 这类目录无需重命名。

## Capture 模型

“一个图片文件”不等于“一次实际拍摄”。数据库使用：

```text
Capture（一次快门）
├── RAW 原片
├── 相机 JPEG
└── Lightroom / PS 修图成片
```

例如下面三个文件应统计为 **1 个 Capture / 3 个文件**：

```text
DSC01234.ARW
DSC01234.JPG
DSC01234-Edit.jpg
```

### v0.1 关联键

优先使用：

1. 相机序列号；无序列号时使用相机型号。
2. `DateTimeOriginal`（退化为 `CreateDate`）。
3. 归一化后的文件名 stem。

修图后缀如 `-Edit`、`_edited`、`-修图`、`-LR`、`-final` 会被去除。

同名文件在不同拍摄时间不会合并，避免相机文件计数器循环后出现 `DSC00001` 重名误判。

若缺失拍摄时间，v0.1 会保守地将主题、父目录和文件名加入键中，宁可少合并也不错误合并。

## 数据库

核心表：

- `libraries`：可扫描的照片库。
- `captures`：真实拍摄事件。
- `files`：物理图片文件和完整 EXIF。
- `scan_runs`：扫描历史。

SQLite 使用 WAL 模式。数据库与原图分离，SPK 最终放在套件私有数据目录中。

## 增量扫描

每次扫描：

1. 遍历允许的图片扩展名。
2. 对比 `absolute_path + size + mtime`。
3. 未变化文件只更新 `last_seen_scan_id`，不重新执行 ExifTool。
4. 新增/变化文件按批次调用 ExifTool。
5. 本轮未见到的旧记录标记 `active=0`，不直接删除历史数据。
6. 清理已经没有任何活动文件的 Capture 空壳。

## v0.1 统计

- 实际拍摄 Capture 数。
- 物理图片文件数。
- RAW 数。
- 已修图 Capture 数与修图率。
- 顶层摄影主题分布。
- 相机和镜头使用分布。
- RAW 光圈分布。
- RAW ISO 分布。
- RAW 实际焦距区间分布。
- RAW 快门速度近似标准档位分布。

## SPK 方向

v0.1 仓库包含 DSM 6 友好的 SPK 骨架。开发版默认寻找系统 `python3` 和 `exiftool`；正式发布前将把固定 Python runtime 与 ExifTool vendoring 到 SPK，避免依赖用户额外安装。

计划的套件数据结构：

```text
/var/packages/photoexifreader/
├── target/         # 程序，只读
└── var/            # config.json / SQLite / 日志 / 后续缩略图缓存
```

## 后续里程碑

### v0.2
- 缩略图缓存（优先 RAW 内嵌预览，不解码完整 RAW）。
- Capture 详情页及 RAW/JPG/修图三态展示。
- 摄影主题、年份、器材、EXIF 交叉筛选。
- 35mm 等效焦距统计。

### v0.3
- GPS 地图。
- XMP/Lightroom 星级和关键词。
- 定时增量扫描。
- 目录规则管理 UI。
- Capture 自动关联置信度与人工修正。

### v1.0
- 打包 Python + ExifTool，无外部运行依赖。
- DSM 6 / DSM 7 分包或兼容构建。
- 正式 SPK 图标、升级/卸载迁移与备份策略。

# Gen8 Photo EXIF Reader

面向 Synology NAS 的个人摄影 EXIF 索引与统计套件（初版）。

目标是直接读取现有照片库，不移动、不重命名、不修改原始照片，把**照片库根目录下的第一级文件夹作为摄影主题**，并将 RAW、机内 JPG 和 Lightroom/Photoshop 修图导出关联到同一次实际拍摄（Capture）。

> 当前版本：`0.1.0`，属于可运行的技术初版 / SPK 骨架，不建议直接对唯一照片库执行任何写入操作。扫描器设计为只读原片，所有状态只写入独立 SQLite 数据库。

## 目前已经实现

- 多照片库配置。
- 顶层文件夹自动作为主题，例如：旅游、散步、拍娃、拍猫。
- RAW：ARW / CR2 / CR3 / NEF / NRW / RAF / ORF / RW2 / DNG / PEF / SRW。
- JPEG / HEIF / TIFF 索引。
- ExifTool 批量读取 EXIF。
- 相机、镜头、焦距、35mm 等效焦距、光圈、快门、ISO、曝光补偿、GPS、尺寸、评级、关键词等字段。
- RAW / 相机 JPG / 修图成片文件角色判断。
- 兼容 `RAW`、`xxxx`、`xxxRAW` 与 `jpg` 等历史目录结构。
- `修图 / 成片 / 导出 / edited / Lightroom / LR` 等目录识别。
- Capture 模型：RAW + JPG + 修图成片可合并为一次真实拍摄。
- `path + size + mtime` 增量扫描，未变化照片跳过 ExifTool。
- 删除/移走文件以 `active=0` 软失效，不修改原文件。
- SQLite WAL 索引数据库。
- Web 总览：实际拍摄数、文件数、RAW、已修图 Capture、主题、器材、光圈、ISO、焦段、快门分布。
- 最近索引文件列表。
- Web 设置照片库和目录关键字。
- DSM 6 x86_64 SPK 开发骨架与构建脚本。

详细设计见 [`docs/DESIGN.md`](docs/DESIGN.md)。

## 本地运行

要求：

- Python 3.9+（开发环境）
- ExifTool 在 `PATH` 中，或者设置 `PHOTOEXIF_EXIFTOOL`

```bash
git clone https://github.com/snailjayxxx/Gen8-PhotoExifReader.git
cd Gen8-PhotoExifReader
./scripts/dev_run.sh
```

浏览器打开：

```text
http://NAS_OR_HOST:9865
```

第一次进入“设置”，例如填写：

```text
我的摄影库 | /volume1/photo
```

保存后点击“扫描照片库”。

也可以指定独立数据目录：

```bash
PHOTOEXIF_DATA_DIR=/path/to/appdata ./scripts/dev_run.sh
```

## 目录示例

```text
/volume1/photo/
├── 旅游/
│   └── 2026名古屋/
│       ├── 名古屋RAW/
│       │   ├── DSC01234.ARW
│       │   └── 修图/
│       │       └── DSC01234-Edit.jpg
│       └── jpg/
│           └── DSC01234.JPG
├── 散步/
├── 拍娃/
└── 拍猫/
```

系统会得到：

```text
主题：旅游
Capture：DSC01234
├── RAW        DSC01234.ARW
├── Camera JPG DSC01234.JPG
└── Edited     DSC01234-Edit.jpg
```

因此“实际拍摄”统计为 1，而“物理图片文件”统计为 3。

## API

```text
GET  /api/health
GET  /api/dashboard
GET  /api/photos?limit=100&theme=旅游&role=raw
GET  /api/settings
POST /api/settings
POST /api/scan
GET  /api/scan/status
```

## 构建开发版 SPK

```bash
./scripts/build_spk.sh
```

输出：

```text
dist/Gen8-PhotoExifReader-0.1.0-x86_64.spk
```

### 当前 SPK 注意事项

`0.1.0` 的 SPK 是开发骨架：当前会优先使用套件内 `runtime/bin/python3`，若不存在则寻找系统 `python3`；ExifTool 同理会优先寻找未来打包的 `vendor/exiftool/exiftool`，否则寻找系统 `exiftool`。

正式发布版计划直接打包固定 Python Runtime 与 ExifTool，使群晖端无需手动安装开发依赖。

## 数据安全原则

- 不移动照片。
- 不重命名照片。
- 不写 EXIF。
- 不写 XMP。
- 不删除原始文件。
- 数据库、日志和未来缩略图缓存在套件独立目录。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## Roadmap

下一步优先级：

1. RAW 内嵌预览缩略图与缓存。
2. Capture 详情页，明确显示 RAW / JPG / 修图三态。
3. 主题 × 年份 × 相机 × 镜头 × 光圈 × 焦距 × 快门 × ISO 交叉筛选。
4. 35mm 等效焦段切换。
5. GPS 地图。
6. Lightroom/XMP 星级与关键词统计。
7. 定时扫描和正式 DSM 6/7 SPK 无依赖打包。

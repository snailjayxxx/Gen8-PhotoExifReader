# Gen8 Photo EXIF Reader

面向 Synology NAS 的个人摄影 EXIF 索引与统计套件（初版）。

目标是直接读取现有照片库，不移动、不重命名、不修改原始照片，把**照片库根目录下的第一级文件夹作为摄影主题**，并将 RAW、机内 JPG 和 Lightroom/Photoshop 修图导出关联到同一次实际拍摄（Capture）。

> 当前开发版本：`0.1.1-0003`。DSM 最低版本目标为 6.1-14715。0003 增加 x86_64 原生诊断回退服务：即使 DSM 上没有可用 Python 3，套件也能保持运行并通过 9865 页面显示启动原因。

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
- DSM 6.1+ x86_64 SPK 构建脚本。
- DSM 6 启动时自动检测套件内 Python、Synology Python3 套件路径和系统 Python。
- Python 缺失/版本过低/后端启动失败时，自动切换到静态链接的原生诊断 Web 服务，避免套件持续显示“停用”。

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

## 数据安全原则

- 不移动照片。
- 不重命名照片。
- 不写 EXIF。
- 不写 XMP。
- 不删除原始文件。
- 数据库、日志和未来缩略图缓存在套件独立目录。

## DSM 6.1+ SPK

```bash
python3 scripts/build_spk_dsm61.py
```

当前 0003 是 x86_64 启动诊断版。构建机需要 `gcc` 并支持 `-static`，用于把原生诊断服务编译成不依赖 DSM 用户空间动态库的单文件 ELF。

套件启动顺序：

1. 套件内 `runtime/bin/python3`
2. Synology Python3 套件常见路径
3. DSM 系统 Python3
4. 若以上 Python 不存在、低于 3.8，或 Python 后端启动后立即退出，则自动启动 `native/diag-server`

诊断日志写入：

```text
/tmp/Gen8PhotoExifReader.log
```

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## Roadmap

1. 将固定 Python Runtime 与 ExifTool 正式封装进 x86_64 SPK。
2. RAW 内嵌预览缩略图与缓存。
3. Capture 详情页，明确显示 RAW / JPG / 修图三态。
4. 主题 × 年份 × 相机 × 镜头 × 光圈 × 焦距 × 快门 × ISO 交叉筛选。
5. 35mm 等效焦段切换。
6. GPS 地图。
7. Lightroom/XMP 星级与关键词统计。
8. 定时扫描和 DSM 7 兼容。

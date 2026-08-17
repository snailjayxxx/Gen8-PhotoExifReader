# DSM 6.1+ 兼容策略

Gen8 Photo EXIF Reader 的最低 DSM 目标为 **6.1-14715**。

## SPK 格式

- 外层 `.spk` 使用 POSIX USTAR，不使用 GNU/PAX 扩展。
- 内层 `package.tgz` 使用 gzip + USTAR。
- DSM 6.1+ x86_64 测试包使用 `arch="x86_64"`。

## v0.1.1-0003 启动诊断

0002 在 DSM 上安装成功但可能一直显示“停用”。根因之一是启动脚本找不到 Python 3 时没有启动任何常驻进程；DSM 随后的 status 检查因此返回未运行。

0003 调整为：

1. 搜索套件内 `runtime/bin/python3`。
2. 搜索 Synology Python3 套件常见路径。
3. 搜索 DSM 系统 Python3。
4. Python 低于 3.8、找不到 Python，或者 Python 后端启动后立即退出时，自动启动套件内静态链接的 x86_64 `native/diag-server`。
5. PID / 启动日志使用 `/tmp/Gen8PhotoExifReader.*`，减少 DSM 6 package 用户对套件目录写权限差异造成的干扰。

诊断页面监听：

```text
http://NAS_IP:9865/
```

诊断日志：

```text
/tmp/Gen8PhotoExifReader.log
```

该原生诊断程序只负责验证 DSM 的 SPK 生命周期、进程状态和 9865 端口，不读取或修改任何照片。

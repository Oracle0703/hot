# 桌面壳接入说明

本文档面向 Electron、Tauri、WinUI 等本地壳层，说明如何消费热点采集系统当前暴露的桌面壳契约。

## 接入目标

| 目标 | 说明 |
| --- | --- |
| 不硬编码路径 | 壳层不再自己猜 `launcher.py`、`status.ps1`、`启动系统.bat` 的位置 |
| 不硬编码调用方式 | 壳层不再自己判断该走 `cmd.exe`、`powershell.exe`、`python` 还是直接执行 exe |
| 同时兼容两种布局 | 同一套逻辑兼容源码运行目录与发布目录 |
| 可离线校验 | manifest 响应可用仓库内 JSON Schema 做本地校验 |

## 契约入口

| 类型 | 路径 | 作用 |
| --- | --- | --- |
| HTTP 接口 | `GET /system/desktop-manifest` | 返回当前实例的导航、服务地址和本地控制面 |
| Schema 文件 | `docs/specs/desktop-manifest.schema.json` | 用于桌面壳侧离线校验、类型生成或回归对比 |
| 示例脚本 | `scripts/desktop_manifest_consumer.py` | 演示如何读取 manifest 并解析出可执行命令 |
| 业务说明 | `docs/specs/api-reference.md` | 描述字段语义 |

## 推荐接入流程

| 步骤 | 动作 | 说明 |
| --- | --- | --- |
| 1 | 读取本地 schema | 启动壳层时加载 `desktop-manifest.schema.json` |
| 2 | 请求 manifest | 调用 `GET /system/desktop-manifest` |
| 3 | 校验响应 | 用 schema 或等价类型系统校验字段完整性 |
| 4 | 渲染导航 | 直接使用 `navigation[]` 生成主导航或菜单 |
| 5 | 控制本地实例 | 对 `control.launch` / `control.probe` / `control.stop` 使用统一调度逻辑 |
| 6 | 展示状态 | 读取 `service.entry_url`、`service.health_url`、`control.probe` 的结果做状态卡片 |

## 字段分工

| 字段组 | 用途 | 桌面壳如何消费 |
| --- | --- | --- |
| `navigation` | 页面导航 | 直接生成菜单、侧边栏或首页快捷入口 |
| `service` | 当前实例的绝对 URL | 用于内嵌 webview、健康检查、打开浏览器 |
| `runtime` | 当前运行根目录 | 用于日志定位、错误提示、诊断上传 |
| `control.launch` | 启动入口 | 当实例未运行时，按 `preferred_path` + `launch_mode` + `preferred_args` 调用 |
| `control.probe` | 状态探测入口 | 用于轮询当前实例是否可用，并拿到结构化 JSON |
| `control.stop` | 停止入口 | 用于安全关闭当前实例 |

## 调用矩阵

| `launch_mode` | 适用场景 | 壳层执行方式 |
| --- | --- | --- |
| `batch-file` | 发布目录中的 `启动系统.bat` / `查看状态.bat` / `停止系统.bat` | `cmd.exe /c <preferred_path> <preferred_args...>` |
| `powershell-file` | 源码目录中的 `status.ps1` / `stop.ps1` | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <preferred_path> <preferred_args...>` |
| `python-script` | 源码目录中的 `launcher.py` | `python <preferred_path> <preferred_args...>` |
| `native-executable` | 发布目录中的 `HotCollectorLauncher.exe` | 直接执行 `<preferred_path> <preferred_args...>` |

## 当前约定

| 控制项 | 源码运行目录 | 发布目录 |
| --- | --- | --- |
| `control.launch.preferred_path` | `launcher.py` | `启动系统.bat` |
| `control.launch.launch_mode` | `python-script` | `batch-file` |
| `control.probe.preferred_path` | `scripts/status.ps1` | `查看状态.bat` |
| `control.probe.launch_mode` | `powershell-file` | `batch-file` |
| `control.stop.preferred_path` | `scripts/stop.ps1` | `停止系统.bat` |
| `control.stop.launch_mode` | `powershell-file` | `batch-file` |

## 关键细节

| 项目 | 说明 |
| --- | --- |
| `preferred_path` | 壳层优先使用的入口文件，已经按当前运行布局做好选择 |
| `preferred_args` | 与 `preferred_path` 配套的推荐参数；壳层应优先使用 |
| `default_args` | 对该控制项普遍成立的默认参数集合；如无特殊需要，可与 `preferred_args` 一致使用 |
| `probe` 在发布目录下 `preferred_args=[]` | 因为 `查看状态.bat` 已内嵌 `--probe --print-json`，壳层不需要重复追加 |
| `stop` 在发布目录下 `preferred_args=["-PrintJson"]` | 因为 `停止系统.bat` 会把参数透传给 `stop.ps1`，壳层仍应追加该参数以拿到结构化结果 |

## 最小调度伪代码

```text
manifest = fetch("/system/desktop-manifest")
validate(manifest, desktop_manifest_schema)

control = manifest["control"]["probe"]

if control["launch_mode"] == "batch-file":
    exec(["cmd.exe", "/c", control["preferred_path"], *control["preferred_args"]])
elif control["launch_mode"] == "powershell-file":
    exec([
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", control["preferred_path"],
        *control["preferred_args"],
    ])
elif control["launch_mode"] == "python-script":
    exec(["python", control["preferred_path"], *control["preferred_args"]])
else:
    exec([control["preferred_path"], *control["preferred_args"]])
```

## 示例脚本

| 用法 | 说明 |
| --- | --- |
| `python scripts/desktop_manifest_consumer.py --manifest-file manifest.json --control probe --print-json` | 从本地文件读取 manifest，并输出 `probe` 命令计划 |
| `python scripts/desktop_manifest_consumer.py --manifest-url http://127.0.0.1:38080/system/desktop-manifest --control stop --print-json` | 直接请求运行中实例的 manifest，并输出 `stop` 命令计划 |

## 推荐实践

| 建议 | 说明 |
| --- | --- |
| 缓存最近一次 manifest | 避免每次点击按钮都重新推断入口 |
| 启动后轮询 `control.probe` | 比单纯等待进程退出/启动更稳，尤其适合壳层状态灯 |
| 优先信任 `preferred_*` 字段 | 不要在壳层重新猜测是否该调 bat、ps1 或 exe |
| 把 schema 随壳层一起打包 | 这样离线环境下也能做响应校验 |
| 记录 `runtime.runtime_root` | 出现异常时便于引导用户回传日志、数据库或配置目录 |

## 当前边界

| 项目 | 现状 |
| --- | --- |
| 多实例管理 | 目前 manifest 面向单实例本地运行，不提供实例列表 |
| 参数自定义 | 当前只暴露推荐参数，不暴露完整 CLI 参数矩阵 |
| 壳层事件回调 | 当前无专门 IPC/事件流，壳层需自行轮询 `probe` 或 `health` |
| 进程托管 | 当前仍由脚本/launcher 管理，不由桌面壳接管生命周期 |

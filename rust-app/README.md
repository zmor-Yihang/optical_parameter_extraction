# THzLab · 太赫兹时域光谱分析

独立的 Windows x64 桌面版，使用 Rust、egui 和 RealFFT，不需要 Python、Qt 或 WebView2。本分支只维护 Rust 版；原 Python 版仍在 `main`。两个版本使用独立的配置和安装路径。

## 构建与运行

在本目录打开终端。编译需要 Rust stable MSVC、Visual Studio 的「使用 C++ 的桌面开发」工作负载和 Windows SDK。运行时优先使用系统的微软雅黑、黑体或宋体；如界面显示方框，请安装 Windows 简体中文字体。

```powershell
cargo run --locked
cargo test --locked
```

安装包需要 Inno Setup 6.3+。默认构建包含静态链接的 MSVC C 运行库，不需要另外分发 VC 运行库。用于个人试用的本地构建命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_installer.ps1
```

安装包位于 `dist/`；发布 EXE 位于 `target/release/`。正式分发前应整理 Rust 依赖声明，可通过 `-DependencyNotices` 随安装包附带。

## 功能与兼容性

- 左侧设置、右侧三组结果，界面固定为浅色，支持专注模式；默认单图，总览双击可打开单图。图表采用 Matplotlib 式导航：默认只读图；「平移」模式左键拖动；「框选缩放」模式左键框选放大、右键框选缩小。再次点击工具或按 Esc 退出；「初始视图 / 后退 / 前进」按子图管理范围历史。仍可悬停读值、手动输入坐标范围和查看数据表。
- 参考/样品导入、逐样品厚度、Tukey 窗和自动定位；导入、分析和导出在后台处理。图表按当前视图准备显示数据，其余指标首次访问时再准备。
- 支持标准 TXT、BT-FTS 扫描 TXT、多种分隔符两列文本、CSV、XLSX（活动工作表）；旧 `.xls` 与 Python 版一样不支持。导出可选光学参数、时域和频域 Excel。对缺少有效延迟参数的 BT-FTS 文件会报错，不会把采样点序号当成 ps。
- Rust 版配置在 `%LOCALAPPDATA%\THzAnalyzerRust\config.json`，不共用 Python 版配置。标准化信号保存在内存中，不再生成临时 TXT；附加元数据不保留。运行状态显示在窗口底部；尚无静默更新和自动下载安装功能。
- 数值回归使用 Python v1.2.0 生成的合成信号基准，覆盖奇偶点数、有无 Tukey 窗、独立厚度与零参考谱。尚未用真实仪器数据作整批对照；建议正式替换原版前先用相同样品比较结果。

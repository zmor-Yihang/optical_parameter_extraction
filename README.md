# 光学参数提取系统 (THzAnalyzer)

基于 Python 与 PyQt6 的太赫兹时域光谱（THz-TDS）数据分析软件，用于从参考/样品时域波形中提取折射率、消光系数、吸收系数及介电特性等光学参数。

## 功能特性

- **统一数据格式**: 支持 BT-FTS 时域扫描 txt、Excel (.xlsx/.xls)、CSV、任意分隔符两列文本等多种来源，自动识别并统一转换为标准两列数据（时间 ps / 幅值），全流程可追溯
- **光学参数计算**: 基于传输函数法计算折射率 n、消光系数 k、吸收系数 α、复介电常数 ε′/ε″ 及介电损耗 tanδ
- **相位分支校正**: 自动消除相位解缠的 2π 整数倍歧义（可选关闭），保证薄样品折射率结果正确
- **Tukey 窗函数**: 可调参数的窗函数去除多次反射干扰，支持按信号单独设置，提供「自动定位」按钮按主脉冲位置自动设置窗口
- **可视化分析**: 时域/频域、光学参数、介电特性三组图表，支持缩放、平移与曲线悬停，结果可在独立子图窗口中对比查看
- **批量处理**: 同时分析多个样品，自动对比显示，多文件计算经过性能优化
- **异步计算**: 后台线程计算与保存，界面不卡顿
- **在线更新检查**: 启动时后台静默检查新版本，支持「帮助 → 检查更新」手动触发；发现新版本后可在应用内下载安装包并启动安装向导（GitHub Releases 托管）
- **配置管理**: 保存与加载分析配置（厚度历史、窗参数、目录等）
- **日志系统**: 完整的操作日志记录

## 系统要求

- Python 3.11+
- Windows 10/11
- uv（Python 包管理器）

## 安装与运行

### 1. 安装 uv（如未安装）

```bash
pip install uv
```

### 2. 克隆项目

```bash
git clone https://github.com/zmor-Yihang/optical_parameter_extraction.git
cd optical-parameter-extraction
```

### 3. 安装依赖

```bash
uv sync
```

### 4. 启动应用

```bash
uv run python main.py
```

## 使用说明

1. **选择参考/样品文件**: 在左侧「参考文件」「样品文件」区域点击添加，或直接拖放文件
   - 支持 BT-FTS 时域扫描 txt，以及两列 Excel（.xlsx）/ txt / csv（第 1 列时间 ps，第 2 列幅值）
   - 若程序无法识别，会提示自行转换为上述标准格式后再导入
   - 多扫描文件自动拆分为多条；样品支持批量添加、删除、清空
2. **设置参数**: 样品厚度（mm，支持逐样品设置）、Tukey 窗函数参数
3. **运行分析**: 点击「运行分析」开始计算光学参数
4. **查看结果**: 右侧标签页分别显示时域/频域、光学参数、介电特性图表，可调整坐标轴范围或在新窗口中查看
5. **保存结果**: 点击「保存光学参数」导出光学参数，「保存时域数据」「保存频域数据」分别导出对应 Excel
6. **检查更新（可选）**: 菜单「帮助 → 检查更新」手动检查新版本；程序启动时也会后台自动检查

## 项目结构

```
optical-parameter-extraction/
├── config/                      # 配置管理
│   ├── config_manager.py        # 配置读写（thz_config.json）
│   └── release.json             # 打包/更新配置（版本号唯一来源）
├── core/                        # 核心业务逻辑
│   ├── calculator.py            # 分析流程编排（加载→预处理→计算→组装结果）
│   ├── physics.py               # 光学参数物理计算（相位分支校正等）
│   ├── preprocessing.py         # 信号对齐与窗函数预处理
│   ├── signal_loading.py        # 参考/样品信号加载
│   ├── standard_format.py       # 统一数据格式：格式识别、解析、标准 txt 读写
│   ├── data_io.py               # 结果导出（txt / Excel）
│   ├── plotting.py              # matplotlib 绘图
│   ├── window_functions.py      # Tukey 窗函数
│   ├── version.py               # 从 config/release.json 读取版本号与更新源
│   ├── updater.py               # 在线更新：拉取版本信息、比较、下载与校验
│   └── exceptions.py            # 自定义异常
├── gui/                         # 图形界面
│   ├── main_window.py           # 主窗口
│   ├── subplot_window.py        # 结果子图独立窗口
│   ├── axis_range.py            # 坐标轴范围控制
│   ├── dialogs.py               # 帮助/关于/更新提示等对话框
│   ├── update_checker.py        # 更新检查与下载工作线程
│   ├── status_bar.py            # 状态栏
│   ├── styles.py                # QSS 样式定义
│   └── worker.py                # 后台工作线程（计算/标准化/保存）
├── scripts/                     # 辅助脚本
│   └── make_version_json.py     # 生成发布用 version.json（自动填版本号/SHA256）
├── utils/                       # 工具
│   ├── app_paths.py             # 打包/开发环境路径定位
│   ├── logger.py                # 日志系统
│   └── matplotlib_setup.py      # matplotlib 中文与主题配置
├── logs/                        # 运行日志（不入库）
├── main.py                      # 程序入口
├── pyproject.toml               # 项目配置与依赖
├── thz_config.json              # 用户配置（不入库）
└── uv.lock                      # 依赖锁定文件
```

## 依赖包

- **PyQt6**: GUI 框架
- **matplotlib**: 数据可视化
- **numpy**: 数值计算
- **openpyxl**: Excel 文件处理

## 打包与安装程序

使用 `build_installer.ps1` 一键构建安装包（PyInstaller + Inno Setup）：

```powershell
.\build_installer.ps1
```

构建依赖：

- Python 3.13 + uv（项目依赖已通过 `uv sync` 安装）
- PyInstaller（脚本会自动检测并按需安装）
- Inno Setup 6（安装：`winget install JRSoftware.InnoSetup`）

构建流程：

1. 从 `config/release.json` 读取版本号，并同步写入 `pyproject.toml`
2. 清理旧的 `output/`、`build/`、`installer-output/` 目录
3. 使用 PyInstaller 以 onedir + windowed 模式打包（同时打入 `config/release.json`），产物为 `output\THzAnalyzer\THzAnalyzer.exe`
4. 使用 Inno Setup 编译 `installer.iss`，生成安装包 `installer-output\install.exe`

安装位置为 `%LOCALAPPDATA%\Thz Analyzer`，无需管理员权限，程序可正常写入 `thz_config.json` 与 `logs/`。若需手动使用 PyInstaller：

```powershell
uv sync --extra build
uv run pyinstaller --onedir --windowed --name THzAnalyzer --distpath output --add-data "config\release.json;config" main.py
```

## 发布新版本

程序通过 GitHub Releases 检查更新，发布流程如下：

1. 更新 `config/release.json` 中的 `version`（版本号唯一来源）。运行 `.\build_installer.ps1` 时会自动同步 `pyproject.toml` 的 `version`，并注入安装包
2. 运行 `.\build_installer.ps1` 构建安装包 `installer-output\install.exe`
3. 运行 `uv run python scripts/make_version_json.py` 生成 `installer-output\version.json`，再用编辑器把 `changelog` 改为实际更新内容（版本号、下载地址与 SHA256 由脚本自动填写）
4. 在 GitHub 仓库 `zmor-Yihang/optical_parameter_extraction` 新建 Release（Tag 建议使用版本号，如 `v1.1.0`，注意不要勾选 pre-release），上传两个资产：
   - `install.exe`：安装包本体
   - `version.json`：版本信息，格式如下
   ```json
   {
     "version": "1.1.0",
     "download_url": "https://github.com/zmor-Yihang/optical_parameter_extraction/releases/latest/download/install.exe",
     "release_date": "2026-08-08",
     "changelog": "- 新增 xxx\n- 修复 xxx",
     "sha256": "脚本自动生成的 SHA256（小写十六进制）",
     "required": false
   }
   ```

程序启动后会自动访问 `releases/latest/download/version.json`，若远端版本高于本地版本则提示更新；`sha256` 缺省时跳过校验，`required` 字段目前仅作预留。

更新源地址可在 `thz_config.json` 的 `update_source` 中覆盖；关闭自动检查可设 `"auto_check_update": false`。

### 版本号规划（语义化版本）

版本号统一采用 `X.Y.Z` 三段格式（更新比较依赖此格式，不能省略段位）：

- **Z（补丁号）**：只修 Bug、不新增功能的微小修复，如 `1.0.0 → 1.0.1`
- **Y（次版本号）**：向后兼容的新功能或改进，如 `1.0.1 → 1.1.0`
- **X（主版本号）**：重大重构或不兼容变更，如 `1.1.0 → 2.0.0`

当前以 `1.0.0` 作为首个正式发布。预发布版（如 `1.1.0-beta`）暂不建议使用——更新比较器会忽略 `-beta` 后缀，可能导致预发布版与正式版无法区分。

## 注意事项

- 数据文件格式：第一列为时间（ps），第二列为电场振幅
- 参考文件与样品文件的时间采样点数应一致，不一致时程序自动截断并给出警告
- 样品厚度单位为毫米（mm），支持为每个样品单独设置
- 频率轴默认显示 0–5 THz，可通过图表工具栏调整
- 首次构建安装包较慢，此后增量编译较快


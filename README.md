# 光学参数提取系统 (Optical Parameter Extraction System)

基于 Python 和 PyQt6 的 THz 时域光谱（THz-TDS）光学参数分析系统，用于处理和分析太赫兹光谱数据。

## 功能特点

- **统一数据格式**: 支持 BT-FTS 时域扫描 txt、Excel (.xlsx/.xls)、CSV、任意分隔符两列文本等多种来源格式，统一转换为两列标准数据（时间 ps / 幅值），全流程可追溯
- **光学参数计算**: 基于传输函数法计算折射率 n、消光系数 k、吸收系数 α、复介电常数 ε' / ε'' 及介电损耗 tanδ
- **Tukey 窗函数**: 可调参数的窗函数，用于去除多次反射干扰，支持按信号单独设置
- **可视化分析**: 时域/频域、光学参数、介电特性三组图表，支持缩放、平移与曲线悬停
- **批量处理**: 支持同时分析多个样品，自动对比显示
- **异步计算**: 后台线程计算与保存，不阻塞界面
- **配置管理**: 可保存和加载分析配置参数（厚度历史、窗参数、目录等）
- **日志系统**: 完整的操作日志记录功能

## 系统要求

- Python 3.11+
- Windows 10/11
- uv (Python 包管理器)

## 安装和运行

### 1. 安装 uv (如果尚未安装)

```bash
pip install uv
```

### 2. 克隆项目

```bash
git clone https://github.com/zmor-Yihang/optical_parameter_extraction.git
cd optical-parameter-extraction
```

### 3. 安装依赖

项目使用 uv 进行依赖管理，运行以下命令安装所有依赖：

```bash
uv sync
```

### 4. 运行应用

```bash
uv run python main.py
```

## 项目结构

```
optical-parameter-extraction/
├── config/                    # 配置管理
│   └── config_manager.py      # 配置读写（thz_config.json）
├── core/                      # 核心业务逻辑
│   ├── calculator.py          # 分析流程编排（加载→预处理→计算→组装结果）
│   ├── physics.py             # 光学参数物理计算
│   ├── preprocessing.py       # 信号对齐与窗函数预处理
│   ├── signal_loading.py      # 参考/样品信号加载
│   ├── standard_format.py     # 统一数据格式：格式识别、解析、标准 txt 读写
│   ├── data_io.py             # 结果 txt 写出
│   ├── plotting.py            # matplotlib 绘图
│   ├── window_functions.py    # Tukey 窗函数
│   └── exceptions.py          # 自定义异常
├── gui/                       # 图形界面
│   ├── main_window.py         # 主窗口
│   ├── dialogs.py             # 帮助/关于对话框
│   ├── standardize_dialog.py  # 数据标准化工具对话框
│   ├── status_bar.py          # 状态栏
│   ├── styles.py              # QSS 样式定义
│   └── worker.py              # 后台工作线程（计算/标准化/保存）
├── utils/                     # 工具
│   ├── app_paths.py           # 打包/开发环境路径定位
│   ├── logger.py              # 日志系统
│   └── matplotlib_setup.py    # matplotlib 中文与主题配置
├── logs/                      # 运行日志（不入库）
├── main.py                    # 程序入口
├── pyproject.toml             # 项目配置与依赖
├── thz_config.json            # 用户配置（不入库）
└── uv.lock                    # 依赖锁定文件
```

## 使用说明

1. **启动应用**: 运行 `uv run python main.py` 启动程序
2. **选择参考/样品文件**: 在左侧"参考文件""样品文件"区域点击"添加"，或直接拖放文件
   - 支持原始格式，选中后自动转换为标准两列 txt（暂存于系统临时目录）
   - 多扫描文件自动拆分为多条，样品支持批量添加、删除、清空
3. **导出标准 TXT（可选）**: 菜单"工具 → 导出标准格式"将当前参考/样品文件复制导出到指定目录
4. **设置参数**: 数据起始行（自动检测）、样品厚度（mm）、Tukey 窗函数参数
5. **运行分析**: 点击"运行分析"按钮开始计算光学参数
6. **查看结果**: 右侧三个标签页分别显示时域/频域、光学参数、介电特性图表
7. **保存结果**: 分析完成后点击"保存结果"或"保存时频域数据"导出为 txt

## 依赖包

- **PyQt6**: GUI 框架
- **matplotlib**: 数据可视化
- **numpy**: 数值计算
- **openpyxl**: Excel 文件处理

## 打包与安装程序

### 1. 使用 Nuitka 打包（推荐）

```powershell
.\build_installer_nuitka.ps1
```

依赖：Python 3.13 + uv、MSVC 构建工具（`winget install Microsoft.VisualStudio.2022.BuildTools`）、Inno Setup 6（`winget install JRSoftware.InnoSetup`）。

产物为 `installer-output\install.exe`，首次编译较慢（约 20~60 分钟），此后增量编译较快。

### 2. 使用 PyInstaller + Inno Setup

先安装构建依赖：`uv sync --extra build`，再用 `uv run pyinstaller --onedir --windowed --name THzAnalyzer --distpath output main.py` 打包，然后用 Inno Setup 编译 `installer.iss`。

安装位置为 `%LOCALAPPDATA%\光学参数提取系统`（无需管理员权限，程序可正常写入 `thz_config.json` 与 `logs/`）。

## 注意事项

- 数据文件格式：第一列为时间(ps)，第二列为电场振幅
- 参考文件与样品文件的时间采样点数应一致，不一致时程序自动截断并给出警告
- 样品厚度单位为毫米 (mm)
- 频率轴默认显示 0-5 THz，可通过图表工具栏调整

## 许可证

此项目采用 MIT 许可证 - 详见 LICENSE 文件

## 更新日志

### v0.2.0 (2026-08-05)
- 修正相位解缠的 2π 分支 Bug（PTFE 类薄样品的折射率原来是错的）
- 修正数据起始行自动检测 off-by-one（原来会少读一行）
- 统一光速常量取值，消除折射率约 0.07% 的系统偏差
- 显式释放 Figure，修复反复分析时内存缓慢增长
- 移除 scipy 与 pandas 依赖，打包体积约 −95 MB
- 窗函数对话框新增「自动定位」按钮，按主脉冲位置自动设置窗口

### v4.6.0 (2026-08-05)
- 统一标准数据格式，支持多来源格式导入（BT-FTS 扫描/Excel/CSV/任意文本）
- 参考/样品文件自动标准化，暂存于系统临时目录，不污染项目目录
- 新增"工具 → 导出标准格式"导出当前文件为标准 txt
- 新增"保存结果"与"保存时频域数据"按钮
- 后台线程异步计算与保存

### v0.1.0 (2024-12)
- 初始版本发布
- 基础光学参数计算功能
- PyQt6 图形界面
- Excel 数据导入导出
- 可视化图表展示

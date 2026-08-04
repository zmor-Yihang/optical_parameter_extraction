# 光学参数提取系统 (Optical Parameter Extraction System)

基于Python和PyQt6的THz光学参数分析系统，用于处理和分析太赫兹光谱数据。

## 功能特点

- **数据导入**: 支持tx和Excel文件(.xlsx)格式的光谱数据导入
- **光学参数计算**: 自动计算折射率、吸收系数等光学参数
- **可视化分析**: 提供交互式图表展示分析结果
- **批量处理**: 支持多个样品文件的批量分析
- **配置管理**: 可保存和加载分析配置参数
- **日志系统**: 完整的操作日志记录功能

## 系统要求

- Python 3.13+
- Windows 11
- uv (Python包管理器)

## 安装和运行

### 1. 安装uv (如果尚未安装)
```bash
pip install uv
```

### 2. 克隆项目
```bash
git clone https://github.com/zmor-Yihang/optical_parameter_extraction.git
cd optical-parameter-extraction
```

### 3. 安装依赖
项目使用uv进行依赖管理，运行以下命令安装所有依赖：

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
├── config/                 # 配置文件
│   ├── __init__.py
│   └── config_manager.py
├── core/                   # 核心计算逻辑
│   ├── __init__.py
│   ├── calculator.py       # 光学参数计算
│   ├── data_io.py          # 数据输入输出
│   ├── exceptions.py       # 自定义异常
│   └── window_functions.py # 窗函数处理
├── gui/                    # 图形界面
│   ├── __init__.py
│   ├── main_window.py      # 主窗口
│   ├── canvas.py           # 绘图组件
│   ├── dialogs.py          # 对话框
│   ├── status_bar.py       # 状态栏
│   ├── styles.py           # 样式定义
│   ├── widgets.py          # 自定义控件
│   └── worker.py           # 后台工作线程
├── utils/                  # 工具函数
│   ├── __init__.py
│   ├── logger.py           # 日志配置
│   ├── icon_helper.py      # 图标工具
│   ├── dynamic_styles.py   # 动态样式
│   └── matplotlib_setup.py # Matplotlib配置
├── logs/                   # 日志文件
├── main.py                 # 程序入口
├── pyproject.toml          # 项目配置
├── thz_config.json         # 应用配置
└── uv.lock                 # 依赖文件
```

## 使用说明

1. **启动应用**: 运行`uv run python main.py`启动程序
2. **导入参考文件**: 点击"浏览"按钮选择参考光谱数据文件
3. **导入样品文件**: 选择需要分析的样品光谱数据文件
4. **设置参数**: 根据需要调整分析参数
5. **开始分析**: 点击分析按钮开始光学参数计算
6. **查看结果**: 分析完成后，结果将在图表中显示

## 依赖包

- **PyQt6**: GUI框架
- **matplotlib**: 数据可视化
- **pandas**: 数据处理
- **numpy**: 数值计算 (通过scipy)
- **scipy**: 科学计算
- **openpyxl**: Excel文件处理
- **auto-py-to-exe**: 打包工具

## 开发说明

项目使用uv作为包管理器，所有依赖都在`pyproject.toml`中定义。

### 开发环境设置
```bash
# 安装开发依赖
uv sync

# 运行应用
uv run python main.py
```

### 构建可执行文件
```bash
# 使用auto-py-to-exe创建可执行文件
uv run auto-py-to-exe
```

### 打包为单个安装包（推荐分发方式）

直接在用户机器上跑 `onedir` 文件夹太麻烦、`onefile` 单 exe 启动又慢。
本项目用 **Inno Setup** 把 `onedir` 程序整体封装成一个 `install.exe`：
用户双击安装、装好的是解压好的程序（启动快），也带正常卸载入口。

1. 安装 Inno Setup 6（免费）：
   ```powershell
   winget install JRSoftware.InnoSetup
   ```
2. 一键构建：
   ```powershell
   .\build_installer.ps1
   ```
   产物为 `installer-output\install.exe`，可直接分发。
3. 安装位置为 `%LOCALAPPDATA%\光学参数提取系统`（无需管理员权限，
   程序可正常写入 `thz_config.json` 与 `logs/`）。

> 手动构建：先 `uv run pyinstaller --onedir --windowed --name THzAnalyzer --distpath output main.py`，
> 再用 Inno Setup Compiler 打开 `installer.iss` 编译。脚本与安装配置见 `installer.iss`。

## 注意事项

- 确保数据文件格式正确（Excel .xlsx格式）
- 程序需要管理员权限才能正常运行某些功能
- 日志文件会自动保存在`logs/`目录下
- 配置文件`thz_config.json`会保存用户的设置

## 许可证

此项目采用MIT许可证 - 详见LICENSE文件

## 支持

如有问题或建议，请通过以下方式联系：
- 提交Issue到项目仓库
- 发送邮件到项目维护者

## 更新日志

### v0.1.0 (2024-12)
- 初始版本发布
- 基础光学参数计算功能
- PyQt6图形界面
- Excel数据导入导出
- 可视化图表展示
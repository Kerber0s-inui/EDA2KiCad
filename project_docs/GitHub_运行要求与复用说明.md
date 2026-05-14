# GitHub 运行要求与复用说明

## 文档目的

这份文档是 `README.zh-CN.md` 的补充版本，
重点说明别人拿到仓库后，真正要准备哪些环境和资源，才能跑起来。

## 本地必须具备的内容

### 1. 仓库内容

- 当前仓库本体
- 如果要使用 `third-party` 策略，还需要：
  - `vendor/altium2kicad`

### 2. 必需软件

- Python 3.11+
- KiCad 10.0.x
- 如果要使用 `third-party`，还需要 Git for Windows 自带 Perl

### 3. 当前代码默认使用的路径

当前代码仍默认这些 Windows 路径：

- `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`
- `C:\Program Files\KiCad\10.0\bin\python.exe`
- `C:\Program Files\KiCad\10.0\bin\kicad.exe`
- `C:\Program Files\KiCad\10.0\share\kicad\template\kicad.kicad_pro`
- `C:\Program Files\Git\usr\bin\perl.exe`

如果你的本机安装路径不同，当前版本仍需要手动修改源码。

## 复用前检查清单

- 安装运行依赖：
  - `python -m pip install -r requirements.txt`
- 如果要跑测试：
  - `python -m pip install -r requirements-dev.txt`
- 只准备受支持的原生 Altium 输入：
  - `.SchDoc`
  - `.PcbDoc`
  - `.PrjPcb`
  - 包含以上文件的 `.zip`
- 确认 KiCad 安装在当前代码预期位置
- 如果要用 `third-party`，确认 `vendor/altium2kicad` 已存在
- 如果要用 `kicad-gui-official`，确认当前是未锁屏的 Windows 桌面会话

## 各策略补充说明

### `pcbnew-api`

- 适合无人值守的 PCB 转换尝试
- 依赖 KiCad Python 运行时
- 有时即使进程带警告退出，也已经产出了有效 `.kicad_pcb`

### `kicad-gui-official`

- 当前仓库里原理图和 PCB 的实际效果最好
- 依赖 Windows 桌面 GUI 自动化
- 不适合无头 CI 或长期后台服务

### `kicad-official`

- 依赖 KiCad CLI
- 仅支持 PCB
- 当前主要作为官方参考路径保留

### `third-party`

- 来源于 `altium2kicad`
- 依赖 `vendor/altium2kicad`
- 依赖 Perl
- 一般来说 PCB 效果优于原理图效果

### `custom`

- 自研原理图路径
- 目前不具备生产级可用性

## 推荐命令

### CLI

```bash
python -m eda2kicad.cli convert "C:\path\board.PcbDoc" --output "C:\path\out" --strategy pcbnew-api
```

### Web

```bash
python -m uvicorn eda2kicad.web.app:app --host 127.0.0.1 --port 8000
```

### 测试

```bash
python -m pytest tests -q
```

## 建议对外表述方式

如果你准备把仓库发到 GitHub，最准确的表述是：

- Windows 优先
- 多策略实验性转换器
- 适合评估和流程原型验证
- 暂不是成熟的通用转换产品

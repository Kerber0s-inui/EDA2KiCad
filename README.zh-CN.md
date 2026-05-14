# EDA2KiCad

[English documentation / 英文说明](README.md)

EDA2KiCad 是一个用于将 Altium 设计数据转换为 KiCad 产物的实验性工具集。
当前仓库集成了多种转换策略，不同策略在转换质量、自动化稳定性和外部依赖方面存在明显差异。

这个项目目前更适合内部评估、转换实验和流程原型验证，
还不是一个“开箱即用、通用、稳定可生产”的成品转换器。

## 当前支持范围

- 原理图输入：
  - 原生 Altium `.SchDoc`
- PCB 输入：
  - 原生 Altium `.PcbDoc`
- 组合输入：
  - `.PrjPcb`
  - 包含 `.PrjPcb`、`.SchDoc`、`.PcbDoc` 的 `.zip`
- 主要输出：
  - `.kicad_sch`
  - `.kicad_pcb`
  - `.kicad_pro`
  - `report.json`

## 策略现状

| 策略 ID | 输入支持 | 当前效果 | 说明 |
| --- | --- | --- | --- |
| `pcbnew-api` | 仅 PCB | 较好 | 基于 KiCad `pcbnew` Python API，适合无人值守 PCB 转换，但上游长期支持存在不确定性。 |
| `kicad-gui-official` | 原理图 + PCB | 较好 | 当前仓库里实际效果最好，但依赖 Windows 桌面 GUI 自动化，不适合作为长期稳定策略。 |
| `kicad-official` | 仅 PCB | 当前实际不可用 | 理论上是未来最值得期待的官方路径，但当前 KiCad CLI 导入能力还不够成熟。 |
| `third-party` | 原理图 + PCB | 原理图较差，PCB 较好 | 来源于 `altium2kicad`，需要 vendored 第三方源码和 Perl。 |
| `custom` | 仅原理图 | 很差 | 自研原理图路径，暂不具备生产可用性。 |

## 第三方组件与许可证说明

本仓库为 `third-party` 转换策略 vendored 了上游 `altium2kicad` 项目，
对应目录为 [`vendor/altium2kicad`](vendor/altium2kicad)。

- 上游项目：`thesourcerer8/altium2kicad`
- 上游仓库：<https://github.com/thesourcerer8/altium2kicad>
- 本地路径：`vendor/altium2kicad`
- 上游许可证：GPL-2.0
- 上游许可证文件：`vendor/altium2kicad/LICENSE`

在对外分发本仓库前，请同时阅读 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
该第三方组件仍然受其原始许可证约束。

## 运行要求

### Python 环境

- Python `3.11` 或更高版本
- `pip`

### 外部工具要求

当前仓库在真实使用上仍然是明显的 Windows 优先，因为部分工具路径仍写死在源码中。

- KiCad `10.0.x`
  - 当前代码默认路径：
    - `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`
    - `C:\Program Files\KiCad\10.0\bin\python.exe`
    - `C:\Program Files\KiCad\10.0\bin\kicad.exe`
    - `C:\Program Files\KiCad\10.0\share\kicad\template\kicad.kicad_pro`
- Git for Windows 自带 Perl，如果要使用 `third-party`
  - 当前代码默认路径：
    - `C:\Program Files\Git\usr\bin\perl.exe`
- vendored `altium2kicad` 源码，如果要使用 `third-party`
  - 当前代码默认路径：
    - `vendor/altium2kicad`

### 各策略额外要求

- `pcbnew-api`
  - 需要 KiCad Python 运行时
  - 仅支持 PCB
- `kicad-gui-official`
  - 需要 Windows
  - 需要未锁屏的桌面会话
  - 不适合无头服务器环境
- `kicad-official`
  - 需要 KiCad CLI
  - 仅支持 PCB
- `third-party`
  - 需要 `vendor/altium2kicad`
  - 需要 Perl
- `custom`
  - 无额外外部可执行依赖
  - 仅支持原理图

## 安装

### 运行依赖

```bash
python -m pip install -r requirements.txt
```

### 开发 / 测试依赖

```bash
python -m pip install -r requirements-dev.txt
```

在 Windows 上如果 `python` 不可用，可以改用 `py`。

## CLI 用法

### PCB 示例

```bash
python -m eda2kicad.cli convert "C:\path\board.PcbDoc" --output "C:\path\output" --strategy pcbnew-api
```

### 原理图示例

```bash
python -m eda2kicad.cli convert "C:\path\design.SchDoc" --output "C:\path\output" --strategy kicad-gui-official
```

### 组合包示例

```bash
python -m eda2kicad.cli convert "C:\path\bundle.zip" --output "C:\path\output" --strategy kicad-gui-official
```

## 启动本地 Web 界面

```bash
python -m uvicorn eda2kicad.web.app:app --host 127.0.0.1 --port 8000
```

然后访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)。

## 运行测试

```bash
python -m pytest tests -q
```

## 当前推荐使用方式

- 做 PCB 转换实验时：
  - 优先尝试 `pcbnew-api`，适合无人值守
  - 如果更看重实际转换质量，可以尝试 `kicad-gui-official`，但要接受 GUI 自动化带来的不稳定性
- 做原理图转换时：
  - 当前仓库里 `kicad-gui-official` 的实际效果最好
  - `third-party` 和 `custom` 更适合作为备选或研究路径

## 已知限制

- 源码里部分工具路径仍写死为 Windows 默认安装位置。
- `kicad-gui-official` 依赖真实 Windows 桌面会话，容易受 GUI 环境影响。
- `kicad-official` 当前仍受 KiCad CLI 导入能力限制，实际不可作为主力策略。
- `pcbnew-api` 有可能已经生成有效 `.kicad_pcb`，但进程仍以警告或异常返回。
- `third-party` 强依赖 vendored `altium2kicad` 和 Perl。
- `custom` 当前不适合生产级原理图转换。
- 所有转换结果都仍需在 KiCad 中人工复核，不能直接视为可投产结果。

## 项目补充文档

更适合发布到 GitHub 的补充说明在 [`project_docs`](project_docs) 下：

- [`GitHub_Runtime_Requirements_and_Reuse_Guide_EN.md`](project_docs/GitHub_Runtime_Requirements_and_Reuse_Guide_EN.md)
- [`GitHub_运行要求与复用说明.md`](project_docs/GitHub_%E8%BF%90%E8%A1%8C%E8%A6%81%E6%B1%82%E4%B8%8E%E5%A4%8D%E7%94%A8%E8%AF%B4%E6%98%8E.md)

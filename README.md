# Codex USB Pager

一个基于 RP2040-Zero 的桌面 USB 状态提示器。它通过 USB CDC 接收电脑端汇总状态，
用 1.3 英寸 ST7789 屏幕显示 Codex 任务状态、并行任务数量和每周余量，并在需要人工
处理或任务完成时通过有源蜂鸣器提示。

本仓库同时包含程序源码、主机端工具、测试、已验证 UF2，以及最终四卡扣树脂外壳的
可编辑模型和打印文件。

## 项目简介

主要能力：

- 将多个 Codex 任务聚合为一个 `RUNNING`、`WAIT`、`DONE` 或 `ERROR` 状态；
- 在屏幕上显示 Blossom 动画、并行任务效果和周余量；
- 通过边沿事件控制蜂鸣器，普通运行和心跳保持静音；
- 提供可编辑 FreeCAD 外壳、STEP 交换模型及前后壳 STL；
- 保留固件、主机端和外壳几何测试，方便后续维护。

## 硬件与接线

核心硬件：

- 控制器：RP2040-Zero；
- 屏幕：1.3 英寸 ST7789 IPS，240 × 240，七针 SPI；
- 蜂鸣器：三针低电平触发有源蜂鸣器；
- 板载状态灯：GP16 上的 WS2812；
- 连接方式：RP2040-Zero USB-C，USB CDC。

| 模块引脚 | RP2040-Zero | 说明 |
| --- | --- | --- |
| 屏幕 GND | GND | 共地 |
| 屏幕 VCC | 3V3 | 不要接 5 V |
| 屏幕 SCL | GP12 | PIO SPI 时钟 |
| 屏幕 SDA | GP11 | PIO SPI 数据 |
| 屏幕 RES | GP10 | 复位 |
| 屏幕 DC | GP9 | 命令/数据 |
| 屏幕 BLK | GP8 | 高电平开启背光 |
| 蜂鸣器 GND | GND | 共地 |
| 蜂鸣器 IO | GP14 | 低电平触发 |
| 蜂鸣器 VCC | 3V3 | 模块供电 |

不要使用裸露的两针无源蜂鸣器。

## USB 状态协议

电脑端通过 USB CDC 发送一行以换行符结束的 ASCII 快照：

```text
STATE <state> RUN=<n> WAIT=<n> DONE=<n> BAL=<token> EV=<event>
```

示例：

```text
STATE RUNNING RUN=2 WAIT=0 DONE=14 BAL=82 EV=NONE
```

- 状态：`IDLE`、`RUNNING`、`WAIT`、`DONE`、`ERROR`；
- 事件：`NONE`、`WAIT`、`DONE`、`ERROR`；
- 8 秒未收到有效快照时，固件进入 `OFFLINE`；
- `RUNNING` 且 `RUN>1` 时显示多任务动画。

## 屏幕与蜂鸣器行为

- `OFFLINE`：六个灰色 Blossom 部件落到白色六边形底部；
- `IDLE/READY`：六个绿色部件缓慢环绕，中央显示周余量；
- `RUNNING`：紫色 Blossom 旋转并带有加速和缩放脉冲；
- 多任务运行：主 Blossom 位于前方，后方叠加模糊彩色层；
- `WAIT`：琥珀色确认画面；
- `DONE`：完成画面每三秒脉冲一次，不显示勾号。

蜂鸣器事件：

- `EV=WAIT`：三次安静短鸣；
- `EV=DONE`：一次安静短鸣；
- `EV=ERROR`：五次安静短鸣；
- `RUNNING`、`IDLE`、`OFFLINE`、心跳和普通工具活动静音。

## 快速使用已验证固件

已打包固件位于：

```text
firmware-release/codex_pager_rp2040.uf2
```

烧录步骤：

1. 按住 RP2040-Zero 的 `BOOT` 键；
2. 连接 USB，或在按住 `BOOT` 时复位；
3. 等待电脑出现 `RPI-RP2` 磁盘；
4. 将 UF2 文件复制到该磁盘；
5. 复制完成后磁盘自动消失，控制器重新启动。

仅修改电脑端 Hook 或聚合逻辑时不需要重新烧录固件。

## 从源码构建固件

需要 Raspberry Pi Pico SDK、CMake 和可用的 ARM GCC 工具链。在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rp2040.ps1
```

构建结果：

```text
build-rp2040/codex_pager_rp2040.uf2
```

固件源码位于 `ports/rp2040-zero/firmware/`，原生行为测试位于
`ports/rp2040-zero/tests/`。

## 主机端工具

需要 Python 3，并安装串口与测试依赖：

```powershell
python -m pip install pyserial pytest
```

主要入口：

- `tools/pager_daemon.py`：聚合任务状态并持续发送 USB 快照；
- `tools/pager_hook_runtime.py`：接收 Codex Hook 事件；
- `tools/session_watcher.py`：读取语义会话事件；
- `tools/pager_runtime.py`：维护多任务运行状态；
- `tools/pager_transport.py`：USB 串口传输；
- `tools/weekly_balance.py`：读取周余量。

启动守护进程：

```powershell
python tools/pager_daemon.py
```

`installed-hooks/` 保存当时安装使用的 Hook 和配置快照。复制或修改 Hook 前，请先阅读
`PROGRAM_HANDOFF.md`，并根据本机 Codex 配置目录调整绝对路径。同一时间只运行一个
`pager_daemon.py` 进程。

## 最终四卡扣外壳

最终模型位于 `enclosure/`：

- 可编辑 FreeCAD：`enclosure/outputs/blossom-enclosure.FCStd`；
- STEP：`enclosure/outputs/blossom-enclosure.step`；
- 前壳 STL：`enclosure/outputs/blossom-front.stl`；
- 后壳 STL：`enclosure/outputs/blossom-rear.stl`；
- 参数化建模源码：`enclosure/cad/`；
- 几何测试：`enclosure/tests/`；
- 审计结果：`enclosure/outputs/audit.json`。

只有 `audit.json` 中 `passed=true`，并且 `checks` 中每一项均为 `true` 时，STL 才可
作为打印候选。

树脂打印建议：

- 倾斜摆放，避免将正反面 Blossom 浮雕和正面六边形承靠边直接贴平台；
- 支撑尽量放在隐藏内表面，避开屏幕承靠面、四个卡扣受力面和滑动导轨；
- 普通壳壁为 1.50 mm；卡扣根部和导轨受力壁不低于 1.30 mm；
- 已知薄桥、支撑和止挡不低于 0.80 mm；
- 清洗、排液并完全固化后再试装，不要强压未固化卡扣。

合盖顺序：

1. 将上方两个公头倾斜插入后壳上方接收槽；
2. 放平前壳；
3. 从底边向上滑动 2.50 mm，直到下方两个卡扣进入浅止动。

USB 开口相对早期基线向上移动 5.00 mm。蜂鸣器完全内置，不设置外部开孔。

## 测试

主机端回归命令：

```powershell
python -m pytest tools/test_pager_runtime.py tools/test_session_watcher.py tools/test_pager_state.py tools/test_codex_log_watcher.py tools/test_pager_transport.py -q
```

外壳源码测试：

```powershell
python -m pytest enclosure/tests -q
```

本次 GitHub 整理按用户要求未重新运行测试；历史交接记录中的最近一次主机端结果为
2026-08-21 的 50 项通过，外壳最终审计文件记录 `passed=true`。

## 目录结构

```text
assets/                 Blossom 原始资源
Core/                   生成后的 Blossom 掩码源码
docs/program-history/   程序设计历史
enclosure/              最终四卡扣外壳源码、测试和输出
firmware-release/       已打包 UF2
installed-hooks/        Hook 安装快照
ports/rp2040-zero/      RP2040 固件和测试
tools/                  电脑端工具和测试
PROGRAM_HANDOFF.md      程序维护交接说明
```

## 维护说明

- 修改前先阅读 `PROGRAM_HANDOFF.md`；
- 保持多任务聚合：单个任务提前完成时必须静音，最后一个活动任务结束后才能发出完成事件；
- 不要随意修改 Blossom 中心、花瓣比例、六边形边界、配色或过渡动画；
- 构建目录、Python 缓存、临时测试目录和对象文件不会纳入版本控制；
- 本仓库不包含旧版外壳基线、旧 ZIP 或工作区中的其他项目。

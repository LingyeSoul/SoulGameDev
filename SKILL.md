---
name: SoulGameDev
description: SoulGameDev — build small, polished games with a deterministic, per-asset content pipeline. Use when building or finishing a game and the work involves procedurally generated pixel art with Pillow, generated audio with synthesizer, one generator module per image or sound, palette/atlas validation, seamless audio loops, data-driven Godot content, headless tests, or Windows/Web/Android delivery. Triggers include "SoulGameDev", "asset pipeline", "procedural pixel art", "generate sprites", "generate audio", "one asset one script", "atlas", "seamless loop", "vertical slice", "ship the game".
license: MIT
---

# SoulGameDev

> 资产是构建产物，不是手工艺品。一个资产一个生成器，数据与绘制分离，生成即可验证，重复运行字节一致。

这套方法来自一个已发布的 Godot 4.7 2.5D 像素肉鸽：所有角色、地块、道具、UI、VFX、BGM、环境声与层主音效都由 Python 生成，没有外部图片或采样。本文只保留可复用的工程约束，不写“艺术感觉”。

## 0. 前置依赖（已安装则跳过）

SoulGameDev 不重复造轮子：以下全局技能是**前置依赖**，本技能直接复用它们的成果，不复制、不重装：

| 前置技能 | 用途 |
|---|---|
| `router` | 先判断该用哪个游戏技能 |
| `create-game-assets` | 美术方向、资产清单、光栅 QA、3D 资产 brief |
| `audio-design` | 总线/混音、动态音乐、ducking、节拍同步 |
| `game-feel` | 屏幕震动、hit-stop、缓动、打击感 |
| `godot-*` | Godot 节点、脚本、物理、UI、导出细节 |

先检查，已存在就直接用：

```bash
npx skills list -g
```

输出里应包含 `router`、`create-game-assets`、`audio-design`、`game-feel`、`godot-export` 等。**已经装好就不要重复执行安装命令。**

`npx skills add` 只用于安装技能包，不用于安装前置依赖。前置包由宿主环境提供；如果检查发现缺失，先让主人安装前置包，不要擅自用它去装依赖。

Python 依赖：

```bash
python -m pip install Pillow numpy scipy soundfile "synthesizer>=0.4"
```

## 1. 不可妥协的架构规则

**一个输出资产 = 一个生成器模块。**

```text
tools/art/actors/player.py          -> art/actors/player.png
tools/art/tiles/layer_01_floor.py   -> art/tiles/layer_01_floor.png
tools/audio/sfx/hit.py              -> art/audio/sfx_hit.wav
tools/audio/ambience/layer_02.py    -> art/audio/ambience_layer_02.wav
```

- 一张 sprite sheet 算一个输出；不要在一个模块里顺手写十张不相关的图。
- 变体（暖焰/蓝焰、普通/精英、intro/death）各自一个模块，共享 `_lib` 与 `_data`，不复制绘图/合成代码。
- `_lib/` 只放通用能力（Canvas、描边、包络、滤波、循环、校验），不含任何游戏内容。
- `_data/` 放调色板、动画帧表、BPM、根音、时长、峰值等数值。
- `build.py` 只发现模块、调用 `build(root)`、合并元数据、写清单；它不画图、不合成。
- 新增资产 = 新增文件，不改构建器。

**为什么：** 单体 `gen_assets.py` 在第二个资产出现后就会变成“改一个角色要重跑全部、冲突不断、无法定位哪个输出坏了”的泥球。独立模块让差异、重生成、失败定位和并行开发都以资产为单位。

**什么时候可以破例：** 只有一次性原型、且明确不会进入生产时。出现第二个资产就拆。

## 2. 快速开始

```bash
# 1) 把模板复制进游戏仓库（拒绝覆盖已有文件）
python <skill-dir>/scripts/scaffold.py --into <project-root> --dry-run
python <skill-dir>/scripts/scaffold.py --into <project-root>

# 2) 安装模板依赖
python -m pip install -r <project-root>/requirements.txt

# 3) 构建全部资产（模板自带一个角色图、一个 UI 面板、一个音效、一段环境循环）
python tools/art/build.py --root . --preview
python tools/audio/build.py --root .

# 4) 只重生成一个资产
python tools/art/build.py --root . --only actors/player
python tools/audio/build.py --root . --only sfx/hit

# 5) 单独运行一个资产模块
python tools/art/actors/player.py
python tools/audio/sfx/hit.py
```

模板产出：

- `art/actors/player.png` + `art/ui/panel.png` + `art/_meta/atlas.json` + `art/_meta/preview_*.png`
- `art/audio/sfx_hit.wav` + `art/audio/ambience_room.wav` + `art/_meta/audio.json`

## 3. 工作流

1. **锁定技术合同。** 原生分辨率、窗口、拉伸、地块、角色尺寸、锚点、调色板、音频格式、碰撞层。只写一份，生成器/运行时/测试都引用它。
2. **盘点现有资产。** 如果已有单体生成器，先按“输出图片/输出音频”建模块，再抽 `_lib` 与 `_data`；迁移后连续构建两次，SHA-256 必须一致。
3. **先做一个代表资产。** 一个角色或一张地块，按真实尺寸、真实背景检查剪影与色板。通过后再做同类家族。
4. **一资产一模块。** 模块只读数据、只写自己的输出、返回 JSON 可序列化的元数据。
5. **构建即校验。** 尺寸、色板、描边、底行、颜色数、音频格式、峰值、时长、循环缝；失败信息带资产路径。
6. **生成清单。** `atlas.json` 描述 sheet/cell/pivot/animations；`audio.json` 描述 key/path/bus/loop。运行时只读清单。
7. **验证阶梯。** 资产构建 → 确定性哈希 → 无头内容/连通性测试 → 端到端流程 → 冒烟截图 → 目标设备。
8. **交付矩阵。** Windows 单文件、Web 单线程、Android debug，至少各启动一次。

## 4. 美术：Pillow

完整规则见 [references/art-pipeline.md](references/art-pipeline.md)。核心：

- 调色板先定；绘制函数只接受角色名（`ink`、`cloak`、`flame_core`），不写 hex。
- 只画整数像素；1px ink 描边；内部 2 阶明暗；禁止抗锯齿、渐变、模糊、非整数缩放。
- 每层/biome 只改 HSV 三个旋钮；语义色（善/恶/危险/魂）跨层恒定。
- 暖色只给灯/火/余烬；一帧里暖色像素 ≤ 1.2%。
- 角色锚点 `bottom-center`，最底一行必须有非透明像素。
- 同一 seed 两次生成必须字节一致。
- 每个模块 `build(root)` 内调用 `verify_sprite`；不通过就抛错，不写“差不多能看”的 PNG。

## 5. 音频：synthesizer

完整规则见 [references/audio-pipeline.md](references/audio-pipeline.md)。核心：

- `synthesizer` 做振荡器层；`numpy`/`scipy` 做噪声、包络、滤波、混音、循环、混响。
- 统一 22050 Hz / mono / PCM16；峰值写进声明；循环音频必须验证首尾样本差。
- 循环 = 多渲染淡出尾巴 + 等功率交叉淡化 + 事件模长回卷 + 旋转到最静窗口。
- SFX 短、一次性；ambience/BGM 长、循环；层主 intro/death 是两个独立输出。
- 长循环转 OGG 进包，WAV 母带排除；短音效保留 WAV；Web 用 Stream 播放。
- 每个模块 `build(root)` 内读回文件并 `verify_audio`；一次性音效跳过 seam，但仍查格式/峰值/时长/边缘阶跃。

## 6. 运行时集成

- `atlas.json` → 运行时构建 `SpriteFrames`/`AtlasTexture`；不要为每张生成图手写 `.tres`。
- `audio.json` → `AudioManager` 按 key 加载；SFX 用 voice pool，BGM/ambience 用双 player 交叉淡化。
- 数据内容（层、敌人、物品、对话）用带 `schema_version` / `kind` 的 JSON；加载即校验，错误带文件、id、字段路径。
- 导出后的 `res://` 只读；运行时写 `user://`。
- 光照用调色板索引位移，不要用黑色半透明叠层；光照 pass 在 y-sort 之后统一做一次。

## 7. 验收：什么算完成

一个资产只有同时满足以下条件才算完成：

- [ ] 有独立模块，路径与输出路径一一对应。
- [ ] 模块能单独运行，也能被 `build.py --only` 选中。
- [ ] 数据在 `_data/`，绘制/合成代码里没有魔法 hex/BPM/时长。
- [ ] 自检通过：尺寸/色板/描边/底行，或格式/峰值/时长/循环缝。
- [ ] 预览图或试听文件已人工检查（原生尺寸、真实背景/总线）。
- [ ] 连续构建两次，产物与清单字节一致。
- [ ] 清单有条目，运行时能按 key 加载。
- [ ] 无头测试与端到端流程没有回归。

发布前再跑 [references/ship-and-verify.md](references/ship-and-verify.md) 的完整清单。

## 8. 反模式

| 反模式 | 后果 | 改法 |
|---|---|---|
| 一个 `gen_assets.py` 画全部 | 改一处全量重跑，冲突与回归无法定位 | 一输出一模块，`build.py` 发现 |
| 生成器里写死颜色/数值 | 换 biome、调平衡要改代码 | 数据进 `_data/` |
| 手改 `art/` 下的 PNG/WAV | 下次构建被覆盖，差异丢失 | 改模块或数据，重新生成 |
| 不固定 seed / 用当前时间 | 每次构建字节不同，无法 diff | 固定 seed，两次构建哈希一致 |
| 抗锯齿/渐变/非整数缩放 | 像素糊、出现调色板外颜色 | 整数像素、nearest、色板子集 |
| 黑色半透明当黑暗 | 破坏“灯是唯一暖色” | 调色板索引位移 |
| 把 WAV 母带打进 Web 包 | 包体暴涨 | OGG 循环，WAV 排除 |
| Web 开线程导出却不会配 COOP/COEP | 空白页 / SharedArrayBuffer 错误 | 单线程导出，或正确响应头 |
| 忘记导出 CJK 字体 | Web 中文全变方块 | 字体随包，验收中文 |
| 运行时写 `res://` | 导出后失败 | 写 `user://` |
| 只跑一个地牢种子 | 连通性 bug 漏网 | 几百个种子 + 断言 |
| 没有非 0 退出码 | CI 永远绿，线上炸 | 测试失败必须返回非 0 |

## 9. 与 awesome-gamedev 技能的分工

| 任务 | 用哪个技能 |
|---|---|
| 先判断该用哪个游戏技能 | `router` |
| 美术方向、资产清单、光栅 QA、3D 资产 brief | `create-game-assets` |
| 总线/混音、动态音乐、ducking、节拍同步 | `audio-design` |
| 屏幕震动、hit-stop、缓动、打击感 | `game-feel` |
| Godot 节点/脚本/物理/UI/导出细节 | `godot-*` |
| 原型限时、Game Jam、Steam/itch 发布 | `prototype-fast` / `game-jam` / `steam-publish` / `itch-publish` |
| **确定性资产生成、一资产一模块、清单/校验/交付** | **本技能** |

本技能不替代引擎技能；它负责“内容怎么被稳定生产出来并验证”，引擎细节交给对应的 `godot-*` 技能。

## 10. 参考与模板

- [references/art-pipeline.md](references/art-pipeline.md)：Pillow 像素规则、调色板、图集 schema、验收门禁、单体迁移。
- [references/audio-pipeline.md](references/audio-pipeline.md)：synthesizer 用法、包络/噪声/滤波、无缝循环、总线、OGG、验收。
- [references/ship-and-verify.md](references/ship-and-verify.md)：技术合同、数据校验、测试阶梯、Windows/Web/Android 构建、发布清单。
- `assets/project-template/`：可直接复制的项目模板；`tools/art` 与 `tools/audio` 各含一个完整示例。
- `scripts/scaffold.py`：把模板复制进现有仓库，拒绝覆盖。

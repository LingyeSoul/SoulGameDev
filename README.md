# SoulGameDev

[English](README.en.md) · **简体中文**

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)

> 一个资产一个生成器，数据与绘制分离，构建即验证，重复构建字节一致。

SoulGameDev 是一个 agent skill 加可复制的项目模板，服务于小型游戏团队的**确定性内容生产**。这套流程来自一个已发布的 Godot 4.7 2.5D 像素肉鸽：所有角色、地块、UI、VFX、音效、环境声和 BGM 都由 Python 生成，没有外部图片，也没有采样包。模板同时提供 Pillow 像素管线、`svgwrite` + `CairoSVG` 的 SVG 矢量管线、可选的 SpriteKiln 8 方向角色接入，以及 synthesizer/numpy/scipy + pyo 的音频管线。

生成内容应该像软件一样工作：模块小、合同明确、输出确定、检查不过就让构建失败。

## 规则

| 规则 | 为什么 |
| --- | --- |
| 一个输出资产 = 一个 Python 模块 | 只重生成一个 sprite，不用全量重跑；失败信息能直接指向一个文件。 |
| 绘制代码不存游戏数据 | 调色板、帧表、BPM、时长、峰值放在 `_data/`。 |
| `build.py` 只做编排 | 发现模块、导入、合并元数据、写清单；它不画图，也不合成音频。 |
| 每个模块校验自己的输出 | 尺寸、色板、峰值或循环缝不对就构建失败；本地产物仅供排查，不得进入发布包。 |
| 连续两次构建字节一致 | 生成资产可以像源码一样 diff、审查和版本管理。 |
| 清单就是运行时 API | 游戏读 `atlas.json` 和 `audio.json`，从不遍历美术目录。 |

## 包含什么

- `tools/art/build.py`：发现 `tools/art/` 下的模块，调用 `build(root)`，把元数据合并进 `art/_meta/atlas.json`，可选输出 4 倍预览。
- `tools/audio/build.py`：对 `tools/audio/` 和 `art/_meta/audio.json` 做同样的事。
- `_lib/`：Canvas、描边、斜面、sheet、SVG 画布、CairoSVG 光栅化、包络、噪声、滤波、pyo 离线渲染、循环构造和校验。
- `_data/`：调色板、动画表、矢量色板、音频 profile 和 pyo profile。
- 三个美术示例模块（两个像素 + 一个 SVG）和三个默认音频模块（含 pyo 示例），全部带校验。
- `scripts/scaffold.py`：把模板复制进已有仓库，拒绝覆盖文件。
- `assets/project-template/scripts/kiln_import.py`：scaffold 后位于项目内 `scripts/kiln_import.py`，把 SpriteKiln 的 8 方向渲染导入 `art/_meta/spritekiln.json`。
- `tools/audio/sfx/pyo_impact.py`：pyo 离线 DSP 示例，默认音频构建会包含它。
- `references/`：管线规则、验收门禁，以及 Windows / Web / Android 交付清单。

## 安装

### 作为 agent skill

```bash
npx skills add LingyeSoul/SoulGameDev -g -y
npx skills list -g
```

本地目录：

```bash
npx skills add <path-to-this-repo> -g -y --copy
```

安装后，agent 可以用 `SoulGameDev` 这个名字调用它。`npx skills add` 只安装技能，不安装 Python 包，也不安装前置技能。

### 前置依赖

- Python 3.12+。
- Pillow、numpy、scipy、soundfile、synthesizer、svgwrite、CairoSVG、pyo：

```bash
python -m pip install Pillow numpy scipy soundfile "synthesizer>=0.4" svgwrite CairoSVG "pyo>=1.1"
```

Windows 上若 CairoSVG 报找不到 cairo，安装 GTK 3 运行时；详见 `references/art-pipeline.md` 第 6.6 节。scaffold 后统一用 `python -m pip install -r requirements.txt`。

scaffold 之后也可以用带版本范围的清单：

```bash
python -m pip install -r requirements.txt
```

- `awesome-gamedev-agent-skills` 技能包（`router`、`create-game-assets`、`audio-design`、`game-feel`、`godot-*`）。SoulGameDev 复用这些技能，不复制它们。用 `npx skills list -g` 检查；缺失时单独安装该技能包。
- 可选：Godot 4.x。模板只产出资源，不绑定引擎。
- 可选：`spritekiln` CLI（`uv tool install "spritekiln[mcp]"`），用于 8 方向骨骼动画角色。完整流程见 `references/spritekiln-pipeline.md`。
- `pyo>=1.1` 是默认音频依赖，需要 Python 3.12+；已包含在 `requirements.txt` 中，不需要额外安装。

## 快速开始

```bash
# 把模板复制进已有游戏仓库（拒绝覆盖）
python <skill-dir>/scripts/scaffold.py --into <project-root> --dry-run
python <skill-dir>/scripts/scaffold.py --into <project-root>

cd <project-root>
python -m pip install -r requirements.txt

# 构建示例资产（含 pyo 示例）
python tools/art/build.py --root . --preview
python tools/audio/build.py --root .

# 校验已导入的 SpriteKiln 清单与文件（未导入时安全跳过）
python scripts/kiln_import.py --root . --check
# 项目必须包含 SpriteKiln 资产时，让缺失清单直接失败
python scripts/kiln_import.py --root . --check --require-manifest

# 只重生成一个资产
python tools/art/build.py --root . --only actors/player
python tools/audio/build.py --root . --only sfx/hit
python tools/audio/build.py --root . --only sfx/pyo_impact

# 单独运行一个生成器（只写自己的文件，不汇总清单）
python tools/art/actors/player.py
python tools/audio/sfx/hit.py
python tools/audio/sfx/pyo_impact.py
```

预期产物：

```text
art/actors/player.png             64x24 sheet，4 帧 16x24
art/ui/panel.png                  32x32 UI 面板
art/vector/sigil.svg              64x64 SVG 矢量源
art/vector/sigil.png              128x128 CairoSVG 派生光栅
art/audio/sfx_hit.wav             0.2 秒，SFX 总线
art/audio/ambience_room.wav       8.0 秒无缝循环，Music 总线
art/audio/sfx_pyo_impact.wav      0.24 秒，SFX
art/_meta/atlas.json              sheets + images + vectors
art/_meta/audio.json              clips + bus + loop
art/_meta/preview_*.png           4 倍预览（带 --preview）
art/_meta/spritekiln.json         8 方向角色清单（导入 SpriteKiln 后）
art/sprites/<name>/qa.json        SpriteKiln QA 记录（导入后）
```

## 一个资产一个模块

```text
tools/art/actors/player.py          -> art/actors/player.png
tools/art/vector/sigil.py           -> art/vector/sigil.svg + art/vector/sigil.png
tools/art/tiles/layer_01_floor.py   -> art/tiles/layer_01_floor.png
tools/audio/sfx/hit.py              -> art/audio/sfx_hit.wav
tools/audio/ambience/layer_02.py    -> art/audio/ambience_layer_02.wav
tools/audio/sfx/pyo_impact.py       -> art/audio/sfx_pyo_impact.wav
```

- 一张 sprite sheet 算一个输出。变体（暖焰 / 蓝焰、普通 / 精英、intro / death）各自一个模块，共享 `_lib` 和 `_data`。
- `_lib/` 只放通用能力，不含游戏内容。
- `_data/` 放调色板、动画表、矢量色板、BPM、根音、时长和峰值。
- 一个 SVG 模块输出一个 `.svg` 源 + 一个 CairoSVG 派生的 `.png`；PNG 必须登记进 `vectors` 清单。
- 新增资产 = 新增文件，不改 `build.py`。
- `--only` 只重生成选中的模块，并合并回已有清单，其它资产不受影响。

## 仓库结构

```text
SoulGameDev/
  SKILL.md                       # agent skill 入口
  references/
    art-pipeline.md              # Pillow/SVG 规则、调色板、图集 schema、门禁
    spritekiln-pipeline.md       # SpriteKiln 8 方向角色、QA、清单桥接
    audio-pipeline.md            # synthesizer、pyo、循环、总线、OGG、门禁
    ship-and-verify.md           # 技术合同、测试、Windows/Web/Android
  assets/
    project-template/            # 可复制的项目模板
      tools/art/                 # 每个图片一个模块（含 vector/sigil.py）
      tools/audio/               # 每个音频一个模块（含 sfx/pyo_impact.py）
      scripts/kiln_import.py     # SpriteKiln 渲染 -> spritekiln.json
      requirements.txt           # Pillow/numpy/scipy/soundfile/synthesizer/svgwrite/CairoSVG/pyo
      .python-version            # 3.12
  scripts/
    scaffold.py                  # 复制模板，拒绝覆盖
  agents/openai.yaml             # skill 元数据
  LICENSE
```

## 合同

参考项目使用 640x360 原生画布、16x16 地块、16x24 角色和 bottom-center 锚点。示例角色模块固定 16x24 单元格，并校验色板子集、1 px 描边、底行和颜色数；合同不同时同步修改这些常量。

**像素**：只画整数像素，颜色来自调色板，1 px ink 描边，内部两阶明暗，禁止抗锯齿、渐变、模糊和非整数缩放。角色每帧最底一行必须有非透明像素。

**矢量**：SVG 必须有显式宽高；颜色只来自 `VECTOR_PALETTE`；禁止外部引用、`<image>`、脚本、`<style>`、`<text>`、`<use>`、滤镜、渐变和 pattern。允许抗锯齿；PNG 由 CairoSVG 在构建期生成，尺寸 = SVG × 正整数 scale。

**SpriteKiln**：YAML 是源；`render` 的 `qa.json` 必须 `ok: true`；8 方向角色通过 `kiln_import.py` 写入 `art/_meta/spritekiln.json`，不混进 `atlas.json`。

**音频**：22050 Hz、mono、PCM16。每个片段声明总线（`SFX`、`Music`、`Master`）以及是否循环。循环片段必须通过接缝检查；一次性片段也要通过格式、峰值、时长和首尾边界幅度检查。`pyo` 是默认依赖（Python 3.12+），输出走同一套 `verify_audio`。

## 验证

每个模块都在 `build(root)` 里调用 `verify_sprite`、`verify_vector` / `verify_raster` 或 `verify_audio`。检查失败会带着资产路径抛错，CI 会失败，也不会发布无效文件。pyo 模块还会拒绝 `graph` 返回 `None` 和渲染静音。

确定性用两次构建来验证。先给 `art/` 做指纹（包含清单），重新构建，再做一次，比较两份结果：

```bash
python -c "import hashlib,pathlib;[print(hashlib.sha256(p.read_bytes()).hexdigest(), p.as_posix()) for p in sorted(pathlib.Path('art').rglob('*')) if p.is_file()]"
```

构建命令：

```bash
python tools/art/build.py --root . --preview
python tools/audio/build.py --root .
```

两次列表必须完全一致。

验收门禁：

- [ ] 尺寸、色板、描边、底行、颜色数通过。
- [ ] SVG 结构、矢量色板、派生 PNG 尺寸/透明度通过。
- [ ] 采样率、声道、位深、峰值、时长、循环缝通过。
- [ ] pyo 模块通过同一套音频门禁。
- [ ] SpriteKiln `qa.json` 为 `ok: true`，`spritekiln.json` 可加载。
- [ ] 连续两次构建的 PNG / SVG / WAV / JSON 字节一致。
- [ ] `atlas.json`、`spritekiln.json` 和 `audio.json` 能被运行时按 key 加载。

## 清单

`art/_meta/atlas.json`：

```json
{
  "sheets": {
    "player": {
      "path": "res://art/actors/player.png",
      "cell": [16, 24],
      "pivot": [8, 23],
      "animations": {
        "idle": { "fps": 6, "frames": [[0, 0], [0, 1]], "loop": true },
        "walk": { "fps": 8, "frames": [[0, 2], [0, 3]], "loop": true }
      }
    }
  },
  "images": {
    "panel": "res://art/ui/panel.png"
  },
  "vectors": {
    "sigil": {
      "svg": "res://art/vector/sigil.svg",
      "raster": "res://art/vector/sigil.png",
      "size": [64, 64]
    }
  }
}
```

`art/_meta/audio.json`：

```json
{
  "clips": {
    "hit":  { "path": "res://art/audio/sfx_hit.wav", "bus": "SFX", "loop": false },
    "room": { "path": "res://art/audio/ambience_room.wav", "bus": "Music", "loop": true }
  }
}
```

`art/_meta/spritekiln.json`（由 `scripts/kiln_import.py` 写入）：

```json
{
  "format": 1,
  "sprites": {
    "knight": {
      "sheet": "res://art/sprites/knight/knight.png",
      "atlas": "res://art/sprites/knight/knight.json",
      "normal": "res://art/sprites/knight/knight_normal.png",
      "emissive": "res://art/sprites/knight/knight_emissive.png",
      "cell": [96, 96],
      "pivot": [48.0, 68.41],
      "directions": ["s", "se", "e", "ne", "n", "nw", "w", "sw"],
      "view": "topdown",
      "animations": {
        "idle": {
          "loop": true,
          "directions": {
            "s": { "row": 0, "frames": [[0, 0]], "durations": [150], "events": {}, "sockets": {} }
          }
        }
      }
    }
  }
}
```

运行时用清单构建 `SpriteFrames` / `AtlasTexture`，音频管理器按 key 加载片段，8 方向角色按动作 + 方向 key 读取 `spritekiln.json`。清单里的 `res://` 前缀来自 Godot 工作流；换引擎时改前缀，再写一个小加载器。

## 交付

发布前按 `references/ship-and-verify.md` 的清单走：无头内容与连通性测试、端到端流程、冒烟截图，以及 Windows / Web / Android 至少各启动一次。

Web 要额外注意：单线程导出，或正确配置 COOP/COEP 响应头；确保 `.wasm` 以 `application/wasm` 返回；随包携带 CJK 字体；用 OGG 循环而不是 WAV 母带。

## 文档

| 文档 | 内容 |
| --- | --- |
| `SKILL.md` | agent 工作流、架构规则、验收清单、反模式 |
| `references/art-pipeline.md` | 像素规则、SVG 矢量管线、调色板、模块合同、图集 schema、迁移 |
| `references/spritekiln-pipeline.md` | SpriteKiln 安装/风格/渲染/QA、清单桥接、8 方向运行时 |
| `references/audio-pipeline.md` | synthesizer 分层、包络、噪声、滤波、pyo、无缝循环、总线、OGG |
| `references/ship-and-verify.md` | 技术合同、数据校验、验证阶梯、构建矩阵、发布卫生 |

## 常见问题

**一定要用 Godot 吗？**
不。模板产出 PNG、WAV 和 JSON。清单使用 `res://` 只是因为工作流来自 Godot；换引擎时改前缀并补一个加载器。

**已有单体生成器还能用吗？**
能。一次迁移一个输出：拆出模块，把数值移进 `_data/`，连续构建两次并比较哈希。每个 reference 都写了迁移顺序。

**scaffold 遇到已有文件怎么办？**
它会中止并列出全部冲突，不覆盖任何文件。先跑 `--dry-run`。

**可以手改 `art/` 下的文件吗？**
不要。下次构建会覆盖。改模块或 `_data/`，然后重新生成。

**什么时候用 SVG，什么时候用 SpriteKiln？**
UI、图标、Logo 用 SVG；需要 8 方向、骨骼/IK、事件帧的角色用 SpriteKiln；像素角色和地块继续用 Pillow。三者可以同时存在，但清单分开：`atlas.json` 管像素/矢量，`spritekiln.json` 管 8 方向角色。

**什么时候用 pyo，什么时候用 synthesizer？**
短音效、简单音调、噪声床和循环用 synthesizer + numpy/scipy；需要复杂多级滤波、颗粒、延迟/混响或参数曲线时用 pyo。pyo 需要 Python 3.12+，已包含在默认依赖和默认音频构建中。

**为什么是 22050 Hz mono？**
体积小，对这个风格够用。需要 44.1 kHz 立体声时，把合同和校验一起改。

**它会替代其他 gamedev 技能吗？**
不会。SoulGameDev 负责确定性内容生产与验证；美术方向、混音、打击感和引擎细节交给 `router`、`create-game-assets`、`audio-design`、`game-feel` 和 `godot-*`。

## License

MIT，见 [LICENSE](LICENSE)。仓库只包含通用占位符和公开依赖名：没有本机路径、凭据或私密 URL。

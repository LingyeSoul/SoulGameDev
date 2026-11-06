# SoulGameDev

> 一个资产一个生成器，数据与绘制分离，生成即可验证，重复运行字节一致。

SoulGameDev 是一个 agent skill + 项目模板，用于小型游戏团队的**确定性内容生产**。它把一套已经跑通的实践固化成可执行约束：

- 用 **Pillow** 逐像素生成美术资产：调色板先行、整数像素、1px 描边、无外部图片。
- 用 **synthesizer + numpy/scipy** 生成音效、环境声与 BGM：固定种子、无缝循环、无外部采样。
- **一个输出图片/音频对应一个 Python 模块**，不再维护一个几百行的单体生成器。
- `build.py` 只发现模块、调用 `build(root)`、合并 `atlas.json` / `audio.json`。
- 每个资产生成后自检；连续构建两次要求字节一致。
- 附带 Windows / Web / Android 交付清单与 Godot 2.5D 集成经验。

## 安装本技能

`npx skills add` 只用于安装技能包；它不负责安装前置依赖。

```bash
# 发布到 GitHub 后
npx skills add <owner>/SoulGameDev -g -y

# 本地开发目录
npx skills add <path-to-this-repo> -g -y --copy

# 确认
npx skills list -g
```

## 前置依赖

- Python 3.10+
- Pillow、numpy、scipy、soundfile、synthesizer
- 已安装的 `gamedev-skills/awesome-gamedev-agent-skills` 技能包（作为前置技能；已装则跳过，本仓库不负责安装它）
- 可选：Godot 4.x。模板只生成资源，不绑定引擎。

安装 Python 依赖：

```bash
python -m pip install Pillow numpy scipy soundfile "synthesizer>=0.4"
```

检查前置技能：

```bash
npx skills list -g
```

输出里应包含 `router`、`create-game-assets`、`audio-design`、`game-feel`、`godot-export` 等。已经装好就不要重复安装；`npx skills add` 只用来安装技能，不要拿它去装前置依赖包。

## 快速开始

把模板复制进一个已有游戏仓库：

```bash
python <skill-dir>/scripts/scaffold.py --into <project-root> --dry-run
python <skill-dir>/scripts/scaffold.py --into <project-root>
```

构建模板自带的示例资产：

```bash
python tools/art/build.py --root . --preview
python tools/audio/build.py --root .
```

只重生成一个资产：

```bash
python tools/art/build.py --root . --only actors/player
python tools/audio/build.py --root . --only sfx/hit
```

单独运行一个生成器模块：

```bash
python tools/art/actors/player.py
python tools/audio/sfx/hit.py
```

## 一个资产一个模块

```text
tools/art/actors/player.py          -> art/actors/player.png
tools/art/tiles/layer_01_floor.py   -> art/tiles/layer_01_floor.png
tools/audio/sfx/hit.py              -> art/audio/sfx_hit.wav
tools/audio/ambience/layer_02.py    -> art/audio/ambience_layer_02.wav
```

- 一张 sprite sheet 算一个输出；变体各自一个模块，共享 `_lib` 与 `_data`。
- `_lib/` 只放通用能力，不含游戏内容。
- `_data/` 放调色板、动画帧表、BPM、时长、峰值等数值。
- `build.py` 不含绘图/合成逻辑；新增资产 = 新增文件，不改构建器。
- `--only` 只重生成选中项，但会合并回已有清单，不会冲掉其它资产。

## 仓库结构

```text
SoulGameDev/
  SKILL.md                       # agent skill 入口
  references/
    art-pipeline.md              # Pillow 像素规则、图集、验收
    audio-pipeline.md            # synthesizer、循环、总线、验收
    ship-and-verify.md           # 数据、测试、Windows/Web/Android
  assets/
    project-template/            # 可直接复制的项目模板
      tools/art/                 # 每个图片一个模块
      tools/audio/               # 每个音频一个模块
      requirements.txt
  scripts/
    scaffold.py                  # 把模板复制进项目，拒绝覆盖
  LICENSE
```

## 模板包含什么

- `tools/art/actors/player.py`：16×24 四帧角色 sheet。
- `tools/art/ui/panel.py`：32×32 UI 九宫格面板。
- `tools/audio/sfx/hit.py`：0.2 秒打击音效。
- `tools/audio/ambience/room.py`：8 秒无缝环境循环。
- `tools/art/_lib/`：Canvas、描边、斜面、sheet、预览、校验。
- `tools/audio/_lib/`：synthesizer 封装、包络、噪声、滤波、循环、校验。
- `tools/art/_data/`、`tools/audio/_data/`：调色板、动画表、音频 profile。

模板采用 22050 Hz / mono / PCM16 音频合同，以及 640×360、16×16 地块、16×24 角色的像素合同。项目可以按自己的规格改，但要把新数值写进同一份合同并同步校验。

## 验证

```bash
# 全部资产 + 4x 预览
python tools/art/build.py --root . --preview

# 音频读回校验
python tools/audio/build.py --root .

# 连续构建两次，对比产物与清单的 SHA-256
```

验收要求：

- 尺寸、色板、描边、底行、颜色数通过。
- 采样率、声道、位深、峰值、时长、循环缝通过。
- 连续两次构建的 PNG/WAV/JSON 字节一致。
- `atlas.json` / `audio.json` 能被运行时按 key 加载。

## 交付

发布前按 `references/ship-and-verify.md` 的清单走：无头内容/连通性测试、端到端流程、冒烟截图，以及 Windows / Web / Android 至少各启动一次。Web 重点检查单线程导出、`application/wasm`、CJK 字体和 OGG 循环音频。

## License

MIT。见 [LICENSE](LICENSE)。

本仓库的源码与文档只包含通用路径占位符、公开依赖名和自写代码；不包含本机绝对路径、用户名、邮箱、密钥、令牌或私密 URL。Git 提交身份使用仓库本地配置的系统身份，不属于内容隐私扫描范围。第三方依赖与字体分别遵循它们自己的许可证。

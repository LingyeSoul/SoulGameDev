# SpriteKiln 管线 / 8 方向角色

> SpriteKiln 是默认安装的高级角色来源：YAML 描述骨架、SDF 形状和动画，渲染成 8 方向或侧视的像素动画。它和 Pillow 管线是**两条并行产线**，共用同一套验收和清单纪律。生成新的角色/敌人资产前，先询问用户是否使用 SpriteKiln，确认后再走本管线。

## 1. 什么时候用

| 需求 | 用哪个 |
|---|---|
| 16×24 像素角色、地块、UI 面板、像素 VFX | Pillow 管线（`references/art-pipeline.md`） |
| 任意分辨率 UI、图标、Logo | SVG 管线（`references/art-pipeline.md` 第 6 节） |
| 需要 8 方向、骨骼/IK、逐帧事件、挂点、法线/自发光贴图的角色 | **SpriteKiln** |
| 侧视平台跳跃角色，需要 run/jump/rise/fall/land 全套 | **SpriteKiln**（`view: side`） |
| 需要复杂位图纹理或手绘细节 | Pillow 或外部 DCC；不要让 SVG 硬拼 |

SpriteKiln 适合“同一角色在 8 个方向、多个动作下保持构造一致”的场景；它不替代单张像素图的快速迭代。**开始一个新角色前先问用户是否使用 SpriteKiln；得到确认前不要运行 `spritekiln init/render`。** 询问示例：“这个角色用 SpriteKiln（8 方向/侧视骨骼动画）还是常规 Pillow/SVG？”

## 2. 安装与锁定版本

默认随项目依赖安装：

```bash
python -m pip install -r requirements.txt
spritekiln --version
```

- 项目的 `requirements.txt` 包含 `spritekiln[mcp]>=0.3,<0.4`；`[mcp]` 让 `spritekiln mcp` 暴露 14 个工具（`pose`、`render`、`review` 等）。
- 也可以全局安装：`uv tool install "spritekiln[mcp]"`；`scripts/kiln_import.py` 会先找 PATH，再找当前 Python 环境的 `Scripts/bin`。
- `[fast]` 额外安装编译渲染器，约 6 倍速；只在确认目标平台可用时加。
- **在项目里记录版本**（例如 `spritekiln==0.3.*`）。不同版本的着色/几何可能变化；升级后必须重新渲染并审查差异，不能当作无变更。

## 3. 项目内初始化

在游戏仓库根目录执行一次：

```bash
spritekiln init --engine godot --ai generic
```

- `--engine` 决定导出目录：`godot` → `assets/spritekiln/`，`unity` → `Assets/SpriteKiln/`，`monogame` → `Content/sprites/`，`generic` → `sprites/`。
- `--ai generic` 写 `AGENTS.md` 和 `.spritekiln/agent/` 指令；有专用客户端时用 `--ai claude,cursor,...`。
- 首次生成前先回答问题，把美术风格写进 `spritekiln.toml`（视角、屏幕高度、方向数、色板、描边、明暗、比例、面部、动画手感）。之后所有资产共用这套风格。

```bash
spritekiln style show
spritekiln style set --height 48 --outline selective --shading soft --directions 8
```

## 4. 授权循环

```bash
spritekiln new knight
spritekiln validate art/specs/characters/knight/knight.yaml
spritekiln pose art/specs/characters/knight/knight.yaml --dirs all
spritekiln pose art/specs/characters/knight/knight.yaml --focus head --dirs all
spritekiln render art/specs/characters/knight/knight.yaml --export
```

- 每次改 YAML 后先 `validate`，错误带 `file:line:column`。
- 用 `pose` 快速看轮廓/方向；`--focus head` 看脸和头发；`--draft` 只用于迭代，不进最终产物。
- `render` 生成 `<name>.png`、`<name>.json`、`<name>_normal.png`、`<name>_emissive.png`、`qa.json` 和 `preview/`。
- **必须看 PNG/GIF**；不能用“数值看起来对”代替肉眼检查。无法看图时用 `spritekiln review` 的数值和 `qa.json`，并在交付说明里注明未做视觉确认。

## 5. QA 门禁

`render` 结束会写 `qa.json`：

```json
{
  "errors": [],
  "warnings": [],
  "ok": true
}
```

- `ok` 必须为 `true` 才能进入项目资源目录。
- `scripts/kiln_import.py` 会再次断言 `ok: true`，并把 `qa.json` 复制到 `art/sprites/<name>/qa.json`；`--render` 的临时目录删除后仍有审计记录。
- 贴边裁剪（`sprite clipped at the edge`）先改 `size`、`camera.center` 或缩小动作幅度；`camera.scale` 是全局合同，不要为单个资产改。
- 颜色数、剪影稳定性、调色板检查也在 `qa.json` / `review.json` 里；把它们贴进交付记录。
- 渲染产物不允许手改；改 YAML 或风格后重渲染。

## 6. 接进 SoulGameDev 清单

SpriteKiln 的 Aseprite JSON 是完整源数据；SoulGameDev 运行时清单是 `art/_meta/spritekiln.json`。用桥接脚本导入：

```bash
# 已经有一份 render
python scripts/kiln_import.py --root . --name knight \
  --render-dir art/specs/characters/knight/out/knight

# 或者先渲染再导入（需要 spritekiln 在 PATH）
python scripts/kiln_import.py --root . --name knight \
  --spec art/specs/characters/knight/knight.yaml --render

# CI/提交前：只校验已存在的清单与文件，不重新渲染
python scripts/kiln_import.py --root . --check
python scripts/kiln_import.py --root . --check --name knight
```

`--check` 会检查：manifest 结构、sheet/atlas/normal/emissive 文件存在、`qa.json` 为 `ok: true`、atlas `meta.size` 与 PNG 一致、`cell`/`pivot` 与 atlas 元数据一致、每帧行列在 sheet 边界内、`loop`/`events`/`sockets` 类型正确。它不重新渲染，也不修改文件。没有 `spritekiln.json` 时 `--check` 打印 “nothing to check” 并返回 0；如果项目必须包含 SpriteKiln 资产，CI 用 `--check --require-manifest` 让它失败。

脚本会：

1. 读取 `qa.json`；`ok` 不为 `true` 直接拒绝导入。
2. 把 `<name>.png`、`<name>.json`、`<name>_normal.png`、`<name>_emissive.png` 和 `qa.json` 复制到 `art/sprites/<name>/`。
3. 把帧名转换成 `[row, column]`，保留每帧 `durations`、`events`、`sockets`。
4. 写入/合并 `art/_meta/spritekiln.json`（按 key 替换，不碰其它角色）。

`--name` 必须与 spec 名一致；不一致直接报错，避免文件名和清单 key 漂移。

清单结构：

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
            "s": {
              "row": 0,
              "frames": [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4], [0, 5]],
              "durations": [150, 150, 150, 150, 150, 150],
              "events": {},
              "sockets": {}
            }
          }
        }
      }
    }
  }
}
```

- `frames` 是 `[row, column]`，与 `atlas.json` 的约定一致。
- `durations` 是毫秒，不是固定 fps；运行时按每帧时长播放。
- `events` 的 key 是动作内帧号；`sockets` 是该方向每帧的 3D 坐标。
- `normal`/`emissive` 是可选的动态光照输入；不需要时忽略。

## 7. 运行时

- 按速度方向选最近的方向 key；没有对应方向时按 `directions` 顺序回退，并在加载时校验。
- 动画名用 `idle`/`walk`/`attack` 这类动作名，方向单独一层，避免 `idle_s` 与 `idle` 两套命名混用。
- 每帧时长来自 `durations`；不要用 `1/fps` 覆盖。
- `events` 在该帧开始时触发；`sockets` 用世界坐标/角色局部坐标时在加载层统一转换。
- 需要法线光照时用 `normal`；需要自发光时用 `emissive`；两者都可以缺失。
- 运行时只读 `spritekiln.json`，不要扫描 `art/sprites/`。

## 8. 与 `atlas.json` 的边界

| 清单 | 内容 | 谁写 |
|---|---|---|
| `art/_meta/atlas.json` | Pillow 图、单张图片、SVG 矢量 | `tools/art/build.py` |
| `art/_meta/spritekiln.json` | 8 方向 SpriteKiln 角色 | `scripts/kiln_import.py` |

不要把同一个角色同时写进两个清单；不要让 `build.py` 每次构建都跑 SpriteKiln（慢且需要外部 CLI）。SpriteKiln 是显式的“生成/重导入”步骤；普通 `build.py` **不会**扫描 `art/sprites/` 或 `spritekiln.json`，CI 运行 `python scripts/kiln_import.py --root . --check` 校验已提交的清单和文件。

## 9. 反模式

| 反模式 | 后果 | 改法 |
|---|---|---|
| 手改 `out/` 或 `art/sprites/` 下的 PNG/JSON | 下次渲染/导入被覆盖 | 改 YAML，重渲染，再导入 |
| 用 `camera.scale` 修单个动作的贴边 | 全项目角色比例漂移 | 改 `size`、`camera.center` 或动作幅度 |
| 忽略 `qa.json` 的 `ok: false` | 上线才发现缺帧/裁剪 | 构建门禁断言 `ok` 为 true |
| 在 `build.py` 里直接调用 `spritekiln` | 构建变慢、无 CLI 环境直接失败 | 用 `kiln_import.py` 显式导入 |
| 升级 SpriteKiln 后不重渲染 | 产物与工具版本不一致，无法复现 | 记录版本，升级后重渲染并审查 diff |
| 用 SVG 硬拼 8 方向逐帧动画 | 文件巨大、时序/事件难维护 | 用 SpriteKiln 或 Pillow sheet |
| 把 SpriteKiln 的 8 方向图塞进 `atlas.json` 的 `sheets` | 动画命名/方向约定冲突 | 独立 `spritekiln.json` |

## 10. 验收清单

- [ ] `spritekiln --version` 与项目记录一致。
- [ ] `spritekiln validate` 通过。
- [ ] `pose --dirs all` 与 `pose --focus head` 已肉眼检查。
- [ ] `render` 的 `qa.json` 为 `ok: true`，并已复制到 `art/sprites/<name>/qa.json`。
- [ ] `kiln_import.py` 生成的 `spritekiln.json` 含正确的 `cell`/`pivot`/`durations`/`events`/`sockets`。
- [ ] `python scripts/kiln_import.py --root . --check` 通过；要求必须有 SpriteKiln 资产时用 `--check --require-manifest`。
- [ ] 连续导入两次，`art/sprites/<name>/` 与 `spritekiln.json` 字节一致。
- [ ] 运行时能按方向 key 和动作 key 加载，事件帧与动作对得上。

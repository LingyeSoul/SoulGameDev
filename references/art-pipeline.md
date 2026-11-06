# 美术管线 / Art Pipeline

> 本文是 SoulGameDev 的美术合同。目标不是“画得好看”，而是**任何一个像素都能被代码复现、被脚本验证、被单独重生成**。

## 1. 三条硬规则

1. **一个输出图片 = 一个生成器模块。**
   - `tools/art/actors/player.py` → `art/actors/player.png`
   - 一张 sprite sheet 算一张图；不要让一个模块顺手写出十张不相关的图。
   - 变体（暖焰/蓝焰、普通/精英）各自一个模块，共享 `_lib` 与 `_data`，不要复制绘图代码。
2. **生成代码与实际数据分离。**
   - 调色板、动画帧表、尺寸、锚点、数值参数放在 `tools/art/_data/`。
   - `_lib/` 只放与具体游戏无关的图元与校验函数。
   - 绘制模块只做“读取数据 → 画 → 保存 → 校验 → 返回元数据”。
3. **构建器只做发现与汇总。**
   - `tools/art/build.py` 不包含任何绘图逻辑。
   - 它按路径排序导入模块、调用 `build(root)`、合并元数据、写 `atlas.json`。
   - 新增资产 = 新增一个文件，不改构建器。

## 2. 目录契约

```text
tools/art/
  _lib/
    pixel_lib.py          # Canvas、描边、斜面、sheet、preview；无游戏内容
    verify.py             # 尺寸/色板/描边/底行/颜色数校验
  _data/
    palette.py            # 角色色板 + biome 派生参数
    animations.py         # 每个 sheet 的帧表、fps、loop
  actors/
    player.py             # 只产出 art/actors/player.png
  tiles/
    layer_01_floor.py     # 只产出 art/tiles/layer_01_floor.png
  props/
    brazier.py            # 只产出 art/props/brazier.png
  build.py                # 发现模块 + 合并 atlas.json
art/
  actors/player.png       # 构建产物
  tiles/layer_01_floor.png
  _meta/atlas.json        # 运行时读取的图集元数据
  _meta/preview_player.png
```

命名规则：模块相对路径去掉 `.py` 就是输出相对路径。`actors/player.py` 只允许写 `art/actors/player.png`。需要写第二张图时，新建第二个模块。

## 3. 单个资产模块的合同

```python
# tools/art/actors/player.py
from pathlib import Path

from tools.art._data.animations import ANIMATIONS
from tools.art._data.palette import PALETTE
from tools.art._lib.pixel_lib import Canvas, sheet
from tools.art._lib.verify import verify_sprite

CELL_W = 16
CELL_H = 24


def _draw(step: int) -> Canvas:
    canvas = Canvas(CELL_W, CELL_H)
    # 只使用 PALETTE 的角色名，不写 hex，不读全局随机数
    ...
    return canvas


def build(root: Path) -> dict:
    frames = [_draw(0), _draw(1)]
    output = root / "art" / "actors" / "player.png"
    sheet([frames], CELL_W, CELL_H).save(output, 1)

    verify_sprite(
        path=output,
        width=CELL_W * len(frames),
        height=CELL_H,
        allowed=set(PALETTE.values()),
        ink=PALETTE["ink"],
        require_alpha=True,
        bottom_row=True,
        max_colors=12,
        outline=True,
    )
    return {
        "kind": "sheet",
        "key": "player",
        "output": "actors/player.png",
        "cell": [CELL_W, CELL_H],
        "pivot": [CELL_W // 2, CELL_H - 1],
        "animations": ANIMATIONS["player"],
    }


if __name__ == "__main__":
    build(Path(__file__).resolve().parents[3])
```

模块约束：

- `build(root)` 是唯一入口，返回可 JSON 序列化的元数据。
- 不修改全局状态；除自己的输出文件与 `art/_meta` 外不写盘。
- 输出路径必须与模块路径对应；构建器会检查文件真实存在。
- 模块可以单独运行：`python tools/art/actors/player.py`。
- 同一个模块内的多帧必须属于同一张 sheet、同一套尺寸与锚点。
- 画布尺寸、帧数、锚点、动画表都是数据；不要把魔法数字散落在绘制函数里。

## 4. 调色板先行

经验值（来自一个 640×360 的 2.5D 像素游戏）：

- **主色板 32 色**，按职责分区：冷色结构 8、光源 5、骨白 4、血/蚀 4、金属 4、语义色 3、UI 4。
- 每层/每 biome 只取 6 个结构锚点，做统一 HSV 变换，再加 2 个恒定语义色，形成 **8 色子板 + 描边**。
- 层间可辨识规则：相邻两层至少满足一项 `|ΔH| ≥ 38°`、`|ΔkV| ≥ 0.15`、`|ΔkS| ≥ 0.35`。
- 语义色（善/恶/危险/魂）跨 biome 恒定，不参与色相偏移；玩家必须能在 0.2 秒内认出信号。
- **暖色预算**：高饱和暖色只允许出现在灯、火、余烬、灯座。一帧 640×360 里暖色像素 ≤ 1.2%，否则“灯不再是黑暗中唯一光源”。
- 绘制函数只接受角色名（`ink`、`cloak`、`flame_core`），不直接写 `#rrggbb`。

派生公式：

```text
H' = (H + ΔH) mod 360
S' = clamp(S * kS, 0, 1)
V' = clamp(V * kV, 0, 1)
```

只调三个旋钮，锚点顺序可以换，用来改变对比曲线。描边永远不参与变换。

## 5. 像素规则

| 规则 | 值 | 原因 |
|---|---|---|
| 原生分辨率 | 640×360（窗口 1280×720） | 所有尺寸、光源半径、UI 以它为准 |
| 地块 | 16×16 | 房间/走廊按格生成 |
| 普通角色 | 16×24 | 含手持道具 |
| 精英/中型 | 24×32 | 剪影更复杂 |
| 大体型 | 32×48 | 比例刻意错误，制造压迫感 |
| 描边 | 1px，固定 ink 色 | 2px 会吃掉 16px 角色的 1/8 |
| 明暗 | 内部 2 阶（灯焰最多 5 阶） | 第 4 阶在 16px 下会变噪点 |
| 过滤 | nearest，关闭 mipmap | 像素画不允许插值 |
| 位移/缩放 | 整数像素；旋转只允许 90° 倍数 | 避免亚像素 |
| 半透明 | 只用固定档（例如 0.72 / 0.45 / 0.22） | 不做逐像素渐变 |
| 抖动 | 只允许光带边界 1px 50% 棋盘 | 防止 dither 滥用 |

剪影三条铁律（敌我辨识）：

1. 敌人在 16px 下必须有一处轮廓缺口；人是闭合的。
2. 敌人的“手”数量为奇数（3 或 5）；偶数会被读成人。
3. 敌人必须有一个超出逻辑包围盒 1px 的部件，破坏网格规整感。

锚点：

- 角色/敌人：`bottom-center`，例如 16×24 → `pivot [8, 23]`。
- 地块：`top-left`。
- 最底一行必须有非透明像素，否则角色会“飘”。
- 灯/武器等定位件不要镜像换边；镜像会破坏“灯在哪一侧 = 我朝向哪”的空间直觉。

动画经验值：

| 动作 | 帧数 | fps | 循环 |
|---|---:|---:|---|
| 待机呼吸 | 4 | 6 | 是 |
| 行走 | 4 | 8 | 是 |
| 攻击 | 4 | 12 | 否 |
| 受击 | 2 | 12 | 否 |
| 死亡 | 6 | 8 | 否 |
| 灯焰闪烁 | 3 | 8 | 是 |
| 粒子 | 6 | 10 | 否 |

## 6. 图集元数据

`build.py` 合并成 `art/_meta/atlas.json`：

```json
{
  "images": {
    "panel": "res://art/ui/panel.png"
  },
  "sheets": {
    "player": {
      "path": "res://art/actors/player.png",
      "cell": [16, 24],
      "pivot": [8, 23],
      "animations": {
        "idle": {"frames": [[0, 0], [0, 1]], "fps": 6, "loop": true},
        "walk": {"frames": [[0, 2], [0, 3]], "fps": 8, "loop": true}
      }
    }
  }
}
```

- `path` 是引擎资源路径；非 Godot 项目把 `build.py` 的 `RESOURCE_PREFIX` 改掉即可。
- `cell` 是单帧尺寸；`pivot` 是帧内像素坐标。
- `animations.frames` 是 `[row, column]`，不是线性帧号；这样加行动画不会改运行时。
- 运行时只读这一个 JSON 构建 `SpriteFrames` / `AtlasTexture`，**不要为每张图手写 `.tres`**。
- JSON 用 `sort_keys=True` 写出，保证两次构建的差异只来自真实内容。

## 7. 每资产验收门禁

每个模块在 `build()` 返回前必须自检；失败信息要包含资产路径和具体原因。

| # | 检查 | 判定 |
|---:|---|---|
| 1 | 尺寸 | 严格等于登记值；sheet 宽 = 单帧宽 × 列数 |
| 2 | 色板 | 所有可见颜色 ⊆ 当前调色板 + ink |
| 3 | 颜色数 | 不超过该资产声明的上限（角色通常 ≤ 12） |
| 4 | 透明度 | 需要透明背景的资产至少有一个透明像素 |
| 5 | 描边 | 任何“透明像素紧邻有色像素”的边界必须先经过 ink；ink 自身可以接透明 |
| 6 | 底行 | 底行至少一个不透明像素 |
| 7 | 可复现 | 连续构建两次，PNG 与 JSON 字节一致 |
| 8 | 人眼 | 缩到原生尺寸、放到真实背景上仍能读出剪影 |

第 8 条只能人眼判断；其余全部自动化。任何一条不过，不进入游戏资源目录。

`preview()` 生成最近邻放大图，只用于人工检查，不参与运行时：

```bash
python tools/art/build.py --root . --preview
# art/_meta/preview_player.png
```

## 8. 从单体生成器迁移

如果项目已经有一个几百行的 `gen_assets.py`，按下面顺序拆，**每一步都要保持输出字节不变**：

1. 把图元（Canvas、描边、斜面、sheet）抽到 `tools/art/_lib/pixel_lib.py`。
2. 把调色板、尺寸表、动画帧表抽到 `tools/art/_data/`。
3. 按输出图片建立模块：一个图片一个文件，先原样搬绘图代码。
4. 每个模块末尾加 `build(root)` 与自检；运行 `python tools/art/<path>.py` 确认能单独生成。
5. 用 `build.py` 替换原单体入口；连续构建两次，对比所有产物的 SHA-256。字节一致才算迁移完成。
6. 删除旧入口，不要保留“两套都能跑”的状态。

单体生成器只允许存在于一次性原型；出现第二个资产时就拆。

## 9. 命令速查

```bash
python -m pip install -r requirements.txt

# 全部资产
python tools/art/build.py --root . --preview

# 只重生成一个资产
python tools/art/build.py --root . --only actors/player

# 单独运行一个模块（不汇总图集）
python tools/art/actors/player.py
```

构建失败时先看模块路径，再看它声明的输出路径；不要绕过校验去改 PNG。

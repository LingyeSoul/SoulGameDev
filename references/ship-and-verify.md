# 交付与验证 / Ship & Verify

> 资产生成得再漂亮，进不了构建、跑不到目标设备、回归测试过不了，都不算交付。

## 1. 先定合同，再写代码

在写第一个生成器之前，把下面这些值写进一个 `docs/` 或 `README` 里的表格。后续所有素材、UI、构建都引用同一份数字：

| 项 | 示例值 | 影响 |
|---|---|---|
| 原生分辨率 | 640×360 | 光源半径、UI 尺寸、插画尺寸 |
| 窗口 | 1280×720 | 默认缩放 2× |
| 拉伸 | `canvas_items` + `expand` | 16:9 到 20:9 都铺满 |
| 地块 | 16×16 | 地牢生成、碰撞、寻路 |
| 角色 | 16×24 | 锚点、碰撞盒、动画 |
| 精英/大型 | 24×32 / 32×48 | 剪影与碰撞 |
| 过滤 | nearest，无 mipmap | 像素清晰度 |
| 像素吸附 | 2D transform/vertices snap | 消除抖动 |
| 调色板 | 32 主色 + 每 biome 8 色子板 | 美术一致性 |
| 音频 | 22050 Hz / mono / PCM16 | 包体与混音 |
| 碰撞层 | player / world / enemy / pickup / hitbox | 物理与查询 |

合同一旦锁定，生成器、运行时和测试都读同一份值。不要在两个地方各写一个 16。

## 2. 数据驱动，加载即校验

内容（层、敌人、灯芯、天赋、对话、房间）放 `data/*.json`，代码只做读取与校验。

统一信封：

```json
{
  "schema_version": 1,
  "kind": "enemies",
  "enemies": []
}
```

规则：

- 字段名、id、枚举值全部 `snake_case`。
- 可选字段用“省略”表达，不写 `null`；只有明确允许的字段才可为 `null`。
- 未知字段忽略（向前兼容）；未知枚举值必须报错。
- id 全局唯一，正则 `^[a-z][a-z0-9_]{2,47}$`。
- 加载失败必须指出**文件、条目 id、字段路径**，不要只打印“数据错误”。
- 每次改 schema 就升 `schema_version`；不兼容变更不能悄悄混过去。
- 目标形态以契约为准做一次迁移，不允许代码长期同时兼容两套字段。

数据驱动的好处不是“少写代码”，而是**平衡表、内容表、测试可以独立于场景树存在**。无头测试能直接读 JSON 做几万条断言，不需要开窗口。

## 3. 验证阶梯

按成本从低到高，每一层都返回非 0 退出码，CI 才能卡住：

| 层 | 命令示例 | 检查 |
|---|---|---|
| 资产 | `python tools/art/build.py --root .` | 尺寸/色板/描边/底行 |
| 音频 | `python tools/audio/build.py --root .` | 格式/峰值/时长/循环缝/首尾边界 |
| 确定性 | 连续构建两次 + `Get-FileHash` / `sha256sum` | 字节一致 |
| 内容 | `godot --headless ... generator_test.tscn` | 3 万级断言：数据、地图连通性、注册表 |
| 交互 | `godot --headless ... touch_test.tscn` | 触控、对话点击、选择框 |
| 流程 | `godot --path . ... playtest.tscn` | 抉择 → 层主 → 下潜 → 事件 → 灯灭 |
| 冒烟 | `godot --path . ... smoke_run.tscn` | 直接进第一层并截图 |
| 人眼 | `capture_screen.tscn` / 实际设备 | 原生尺寸、真实背景、目标浏览器 |

经验：

- 地牢生成至少跑几百个种子，断言“起点到终点连通、房间不重叠、Boss 房可达”。只跑一个种子等于没测。
- 无头测试要显式 `quit()` 并返回非 0；不要依赖引擎退出码的默认行为。
- 测试脚本停止播放器、释放资源，避免半播放的 WAV 被报告成泄漏。
- 测试用的截图/预览放 `art/_meta/`，不进运行时资源。

## 4. 构建矩阵

### Windows 单文件

```bash
godot --headless --export-release "Windows Desktop" build/win/game.exe
```

- PCK 嵌入 exe，减少“exe 找不到 pck”的支持成本。
- 官方模板约 104 MB；用源码编译的精简模板可把导出 exe 降到约 35 MB。
- 版本号从 `project.godot` 的 `config/version` 读取，构建脚本不要再手写一份。
- 首次编译模板会拉 Godot 源码与 scons，放 `.buildtools/` 并加入忽略。

### Web 单线程

```bash
godot --headless --export-release "Web" build/web/v<version>/index.html
```

关键设置：

- 渲染器 `gl_compatibility`；目标浏览器需要 WebGL 2.0。
- 单线程导出（`nothreads`）不需要 COOP/COEP，可直接放 itch.io、GitHub Pages、Netlify、Cloudflare R2。
- 版本目录 `v<version>/` + 入口跳转页 + `_headers`：入口不缓存，`wasm/pck/js/png` 一年 immutable。
- 首包瓶颈是 `.wasm`；用构建 profile 裁掉未使用类，wasm 可从约 39.5 MB 降到 23.9 MB。
- 自定义 `shell.html` 做“点击开始”门，用户手势后再创建 AudioContext。
- 中文字体必须随包导出：Inter + CJK fallback；把 `art/ui/fonts` 排除会让中文全变方块，这是发布阻断项。
- `audio/general/default_playback_type.web=0`（Stream）；否则单线程下循环音频与总线可能静音。
- 长循环音频转 OGG，WAV 母带从导出预设排除。
- 无痕模式/第三方 iframe 的存储限制会让 `user://` 存档不持久；验收时要在目标环境确认。
- 标签页失焦会暂停；全屏/鼠标捕获只能在输入事件回调里请求。

### Android

```bash
godot --headless --export-debug "Android" build/android/game.apk
```

- 模板 `android_debug.apk` 必须与引擎版本完全一致。
- `ANDROID_HOME` / `ANDROID_SDK_ROOT` 指向 SDK；编辑器的 Android SDK Path 也要指同一目录。
- 全屏适配：`screen/immersive_mode` + `screen/edge_to_edge`，拉伸 `expand`。
- 背景与世界铺满 16:9–20:9；菜单保持在 640×360 安全画框内；HUD/对话框/触控按钮避让刘海与手势条。
- 触控按钮常开，桌面可在设置里关闭；没有主动技能时按钮自动隐藏。

## 5. 像素与 2.5D 集成

- 全局 `default_texture_filter=0`（nearest），关闭 mipmap。
- `snap_2d_transforms_to_pixel` 与 `snap_2d_vertices_to_pixel` 打开，避免半像素抖动。
- 2.5D 俯视斜角用 `y_sort_enabled`，墙/道具以底边为原点；玩家和敌人都按 baseline y 排序。
- 地块只画“顶面 + 南立面”两个面；16×16 图块的立面固定 8 px，不做其他高度。
- 光照用调色板索引位移，不要用黑色半透明叠一层：后者会产生调色板外颜色，破坏“灯是唯一暖色”。
- 光照 pass 放在 y-sort 之后统一做一次，不要每个精灵各算一次。
- 自发光（魂青、祭坛供物、灯焰）跳过光照 pass。
- 受击闪白用 `sprite_flash` shader 或索引 +1，持续 1 帧（约 83 ms），不要做渐变。

## 6. 验收清单

发布前逐条勾：

- [ ] 资产构建无警告；所有模块单独运行都能生成。
- [ ] 连续构建两次，PNG/WAV/JSON 字节一致。
- [ ] 图集尺寸、cell、pivot、动画帧数与运行时读取一致。
- [ ] 用 `--only` 重生成单个资产后，清单仍保留其它资产。
- [ ] 音频清单的 key、bus、loop 与代码调用一致；没有孤儿文件。
- [ ] 无头内容测试与地牢种子测试通过（非 0 退出码会被 CI 捕获）。
- [ ] 端到端流程测试通过：标题 → 驿站 → 下潜 → 战斗 → 抉择 → 下一层 / 死亡 → 回驿。
- [ ] Windows / Web / Android 至少各启动一次；Web 在目标浏览器打开控制台无 WebGL/音频错误。
- [ ] Web 首包大小在目标平台限制内；`.wasm` 用 `application/wasm`，`.pck` 用 `application/octet-stream`。
- [ ] 中文在 Web 端不显示方块。
- [ ] 刷新后存档仍在（浏览器允许存储）。
- [ ] 触屏设备上按钮不压刘海/手势条，菜单在安全画框内。
- [ ] 所有素材有来源/生成说明；没有把私密路径、用户名、密钥写进仓库。

## 7. 发布卫生

- 生成器是唯一事实来源；不要手改 `art/` 下的 PNG/WAV 后再提交。要改就改模块或数据。
- 调色板、动画表、音频 profile 改动后，必须重新构建并跑校验。
- 大文件（WAV 母带、模板、构建产物）不进仓库；在 `.gitignore` 与导出预设里排除。
- 保留生成器的确定性：固定 seed、固定采样率、固定 Python/依赖版本范围。
- 记录依赖版本；`synthesizer`、Pillow、numpy、scipy、svgwrite、CairoSVG、pyo 的大版本变化可能改变输出字节。
- 每加一个资产，问一次：它是“这张图/这段声音”的独立模块，还是又一个塞进单体生成器的例外？如果是后者，拆掉。

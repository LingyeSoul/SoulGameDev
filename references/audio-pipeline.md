# 音频管线 / Audio Pipeline

> 目标：**每一段声音都能被代码重新合成、被读回验证、被单独重生成**。不依赖外部采样，不产生版权风险。

## 1. 三条硬规则

1. **一个输出音频 = 一个生成器模块。**
   - `tools/audio/sfx/hit.py` → `art/audio/sfx_hit.wav`
   - `tools/audio/ambience/layer_02.py` → `art/audio/ambience_layer_02.wav`
   - `tools/audio/music/bgm_boss.py` → `art/audio/bgm_boss.wav`
   - 层主的 intro/death 是两个文件，就两个模块；共享 profile，不共享输出。
2. **合成代码与数值数据分离。**
   - BPM、小节数、根音、和声进行、增益、时长、峰值放 `tools/audio/_data/profiles.py`。
   - `_lib/audio_lib.py` 只放振荡器封装、包络、噪声、滤波、循环、校验。
   - 资产模块只做“读 profile → 合成 → 写文件 → 校验 → 返回元数据”。
3. **构建器只做发现与汇总。**
   - `tools/audio/build.py` 不合成任何声音；它写 `art/_meta/audio.json` 清单。

## 2. 依赖与格式合同

```bash
python -m pip install numpy scipy soundfile "synthesizer>=0.4"
```

`synthesizer` 负责音调层（振荡器 + 双振荡器失谐 + 低通/高通/带通 + LFO），`numpy`/`scipy` 负责噪声床、包络、滤波、混音、循环与混响。

统一格式（可按项目改，但必须写进校验）：

| 项 | 值 |
|---|---|
| 采样率 | 22050 Hz |
| 声道 | 单声道 |
| 位深 | 16-bit PCM WAV |
| 峰值 | 0.20–0.85，通常音乐 0.55、SFX 0.50–0.75 |
| 循环 | `ambience_*` / `bgm_*` 必须无缝；一次性音效不要求 |
| 命名 | `sfx_<action>.wav`、`ambience_<place>.wav`、`bgm_<mood>.wav`、`boss_intro_<tag>.wav` |

单声道不是省事，是像素游戏的空间一致：所有声音从同一个“灯下”位置发出，不制造假的左右声场。

## 3. 声音分层

| 层 | 时长 | 作用 | 循环 |
|---|---|---|---|
| SFX | 0.05–1.5 s | 挥击、命中、受伤、拾取、UI | 否 |
| Stinger | 1.5–3.5 s | 层主登场/消散、渡口钟、记忆闪回 | 否 |
| Ambience | 8–15 s | “这个房间是什么” | 是 |
| BGM | 10–32 s | “这一段路在往哪里走” | 是 |

同一个场景可以叠 ambience + BGM；BGM 负责旋律，ambience 负责空间。不要让 BGM 盖住预警音与命中音——战斗信息走 SFX 总线。

## 4. 用 synthesizer 做音调层

```python
from synthesizer import FilterType, Synthesizer, Waveform
import numpy as np


def tone(waveform, frequency, duration, cutoff, resonance, detune, second_volume, rate, seed):
    synth = Synthesizer(
        osc1_waveform=waveform,
        osc1_volume=1.0,
        use_osc2=detune > 0.0,
        osc2_waveform=waveform,
        osc2_volume=second_volume,
        osc2_detune=detune,
        filter_type=FilterType.lowpass if cutoff is not None else None,
        filter_cutoff=cutoff if cutoff is not None else 1000.0,
        filter_resonance=resonance,
        rate=rate,
        seed=seed,
    )
    return synth.generate_constant_wave(frequency, duration)
```

经验：

- **低频撞击**：`sine` 90→55 Hz + 快速指数包络 + 低通 500 Hz。
- **金属/钟**：非谐波分音（1.0 / 2.01 / 2.99 / 4.18 倍）各自不同衰减，比单一正弦更像青铜。
- **铜管**：1–8 次谐波按 `1/h` 叠加，慢起音 + 中段保持。
- **拨弦**：1–7 次谐波，按 `1/h^(1.35+亮度)` 衰减，指数包络 0.16–0.36 s。
- **失谐**：双振荡器 3–6 cents 会产生缓慢拍频，适合玻璃、镜面、恐惧。
- 每次调用传入固定 `seed`；不要用当前时间。

## 5. 包络、噪声、滤波

```python
def adsr(length, attack, decay, sustain, release, rate):
    ...

def exp_env(length, attack, decay, rate):
    time = np.arange(length) / rate
    env = np.exp(-time / decay)
    env[:max(1, int(attack * rate))] *= np.linspace(0.0, 1.0, max(1, int(attack * rate)))
    return env
```

噪声颜色：

- `white`：全频，适合纸、玻璃、打击瞬态。
- `pink`：80–2400 Hz 带通，适合风、空气、远处人群。
- `brown`：积分并去趋势，适合低频水床、地下空间。

常用组合：

| 目标 | 配方 |
|---|---|
| 挥击 whoosh | 白噪声 + 3.2k→0.5k 低通扫频 + 极短包络 |
| 命中 | 90 Hz 正弦 thud + 600–5200 Hz 带通 crack |
| 受伤 | 196 Hz square 主体 + 98 Hz sine 尾巴 |
| 拾取 | 1046 Hz + 1568 Hz 两个正弦，第二个延迟 50 ms |
| 记忆 | 523 Hz 钟 + 784 Hz 五度 + 3–8k 微光噪声 |
| 死亡 | 49 Hz drone + 900→90 Hz 棕噪声风 + 稀疏颗粒 |
| 下潜 | 55 Hz 低频 + 700→120 Hz 空气 + 392 Hz 钟 |

滤波只用 `scipy.signal.butter(..., output="sos")` + `sosfilt`，不要手写不稳定的递归滤波。

## 6. 无缝循环

循环不是“首尾淡入淡出”，而是让循环点两侧来自连续信号。推荐四步：

1. **多渲染一个淡出尾巴**：生成长度 `length + fade`。
2. **等功率交叉淡化**：把 `[length, length+fade]` 的尾巴淡入头部，头部同时淡出。

```python
ramp = np.linspace(0.0, np.pi / 2.0, fade_count)
looped[:fade_count] = tail * np.sin(ramp) + looped[:fade_count] * np.cos(ramp)
```

3. **事件环形放置**：心跳、铃、木鱼、石裂等一次性事件如果跨过循环点，用 `add_at` 的模长回卷写入开头，不要截断。
4. **把缝旋转到最安静处**：`rotate_to_quiet(looped, 0.04, rate)` 找 40 ms 内 RMS 最低的窗口，整体 roll 到开头。旋转一个已经成立的循环不会破坏连续性。

混响也要环形：环境层的混响尾巴用 FFT 环形卷积，或写回时对缓冲长度取模，避免在缝上被截断。

## 7. 响度与总线

- 所有文件写盘前归一化到声明峰值；不要靠运行时增益救一个 -30 dB 的文件。
- 峰值不是响度；同时记录 RMS，避免“峰值一样但听起来一响一轻”。
- 总线：`Master` / `Music` / `SFX`。
  - 音乐与环境声走 `Music`，设置里的“音乐”滑杆同时控制两者。
  - 音效与预警走 `SFX`，不能被 BGM 盖住。
- 播放器池：8 个 SFX voice 轮转，重叠命中不会互相切断。
- 交叉淡化：进层 0.9 s、进层主 1.1 s、层主消散 1.8 s、灯灭 1.2 s；两条 `AudioStreamPlayer` 轮换，同一组层内切层不重头播放。
- BGM 参考音量：普通层 -21 dB、层主 -16 dB、标题/驿站 -20/-21 dB。

## 8. Web 与压缩

- **长循环用 OGG**：15 条母带 WAV 9.31 MB → 0.98 MB。Godot 导入后不会自动开循环，运行时设置 `AudioStreamOggVorbis.loop = true`、`loop_offset = 0`。
- **短音效保留 WAV**：避免解码延迟；UI、命中、受伤这类 <0.5 s 的声音尤其明显。
- 把 WAV 母带从导出预设里排除，只把 OGG 打进 PCK；否则 Web 包会被母带撑大。
- Web 音频使用 Stream 播放：`project.godot` 里 `audio/general/default_playback_type.web=0`。Godot Web 默认的 Sample 模式在单线程导出下会让循环音频/总线静音。
- 浏览器要求用户手势后才能启动 AudioContext；标题页放一个“点击开始”的启动门，点击后再创建/恢复音频。

## 9. 每资产验收门禁

每个音频模块在 `build()` 返回前读回文件并自检：

| # | 检查 | 判定 |
|---:|---|---|
| 1 | 采样率 | 等于声明值（通常 22050） |
| 2 | 声道 | 单声道 |
| 3 | 位深 | `PCM_16` |
| 4 | 峰值 | 在 `[peak_min, peak_max]` 内 |
| 5 | 时长 | 在声明区间内 |
| 6 | 循环缝 | 循环音频 `|first - last| <= seam_max`（经验值 0.04） |
| 7 | 边缘阶跃 | 首/尾 10 ms 内最大相邻样本差不超过声明值 |
| 8 | 可复现 | 连续构建两次，WAV 与清单字节一致 |

一次性音效把 `seam_max` 设为 `None`，但仍然检查峰值、时长、格式与边缘阶跃。

## 10. 清单与运行时

`tools/audio/build.py` 写出 `art/_meta/audio.json`：

```json
{
  "clips": {
    "hit": {
      "path": "res://art/audio/sfx_hit.wav",
      "bus": "SFX",
      "loop": false
    },
    "room": {
      "path": "res://art/audio/ambience_room.wav",
      "bus": "Music",
      "loop": true
    }
  }
}
```

运行时按 key 加载，不要在主逻辑里散落文件路径。加载循环音频时统一设置 loop，避免每个调用点各写一遍。

Godot 侧建议：

- `AudioManager` 自动加载清单，SFX 用 voice pool，ambience/BGM 各用两条 player 做交叉淡化。
- 循环 OGG 的 loop 标志在运行时设置，导入器保持默认。
- 层号到文件名一一对应：第 N 层 → `ambience_layer_0N`；不要用“大概相似”的名字。
- 层主音效按 `boss_intro_<tag>` / `boss_death_<tag>` 拼接，`tag` 必须在 profile 与音频模块中一致。

## 11. 从单体生成器迁移

和美术一样，迁移必须保持字节一致：

1. 抽出 `_lib/audio_lib.py`（包络、噪声、滤波、混音、循环、校验）。
2. 把 BPM/根音/和声/增益/时长抽到 `_data/profiles.py`。
3. 一个输出文件建一个模块，先原样搬合成代码。
4. 每个模块加 `build(root)` 与读回自检；单独运行确认能生成。
5. 用 `build.py` 替换单体入口，连续构建两次对比 SHA-256。
6. 删除旧入口。

## 12. 命令速查

```bash
python -m pip install -r requirements.txt

# 全部音频
python tools/audio/build.py --root .

# 只重生成一段
python tools/audio/build.py --root . --only sfx/hit

# 单独运行一个模块
python tools/audio/sfx/hit.py
```

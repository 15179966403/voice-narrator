# 🎙️ Standalone Voice Narrator (独立旁白人声生成器)

一个轻量、严谨、开箱即用的广播级语音生成系统。完全独立于任何外部项目，拥有专属的 Python 虚拟环境与自包含音频处理算法（无需引用或复用外部代码）。

---

## 🌟 核心特性

1. **智能分句断句**：自动识别多行段落、中英文标点（`。！？；，`），保证人类自然的呼吸气口；
2. **神经网络语音合成**：采用高品质神经语音（Edge-TTS），具备细腻的重音与古典质感；
3. **精准物理时长测算**：每一句话在合成后经过声学边界裁切与毫秒级时长测定，自动输出分秒对齐的时间轴清单（`timeline.json`）；
4. **声学首尾留白与平滑余韵（Anti-Cutoff Padding）**：
   * **首部缓冲（Lead-In Cushion）**：默认添加 `0.25s` 前置微小静音，避免第一句话第一个字被播放器起调吞字；
   * **尾部余韵（Lingering Tail Buffer）**：末尾最后一句施加 `120ms` 余弦平滑衰减，并附加 `1.8s ~ 2.0s` 舒缓留白，彻底解决音频戛然而止、“突然断电”般的突兀截断感；
5. **广播级母带处理（Mastering）**：
   * 动态范围压缩（Vocal Compression，提升人声厚度与中频质感）；
   * 峰值软膝限制器（Soft-Knee Peak Limiting，彻底避免数码破音失真）；
   * ITU-R BS.1770 / EBU R128 标准化（严格锚定在影视广播标准的 **-14 LUFS** 响度）；
6. **多并发高性能批处理**：长篇大论（数十至上百句）自动异步并发合成，秒级极速成片。

---

## 🚀 快速使用方法

进入该目录后，直接运行：

### 1. 命令行直接传入文本
```powershell
.\.venv\Scripts\python generate.py "天行健，君子以自强不息。地势坤，君子以厚德载物。"
```

### 2. 读取文本文件（如千古长文）
```powershell
.\.venv\Scripts\python generate.py --file tengwangge_xu.txt --voice zh-CN-YunjianNeural
```

### 3. 自定义参数调整（音色、语速、停顿与尾部余音）
```powershell
.\.venv\Scripts\python generate.py --file daodejing_chapter1.txt `
  --voice zh-CN-XiaoxiaoNeural `
  --rate -4% `
  --pause 0.6 `
  --lead 0.3 `
  --tail 2.0 `
  --out output/my_master.wav `
  --json output/my_timeline.json
```

---

## 🎭 推荐常用播音音色

| 音色名称 | 语言 / 风格 | 特点描述 |
|---|---|---|
| `zh-CN-YunjianNeural` | 中文男声 / 影视史诗 | 浑厚庄严、气吞山河、极具历史厚重感，适合长篇巨作 |
| `zh-CN-YunxiNeural`（默认） | 中文男声 / 纪录片解说 | 清晰沉稳、叙事感极佳、抑扬顿挫 |
| `zh-CN-XiaoxiaoNeural` | 中文女声 / 知性温暖 | 吐字圆润、温润典雅、适合散文、经典哲学与情感叙述 |
| `zh-CN-YunyangNeural` | 中文男声 / 严谨新闻 | 专业播音员质感、客观端正 |
| `en-US-ChristopherNeural` | 英文男声 / 纪录片 | 磁性低沉、经典电影旁白质感 |

---

## 📂 输出物结构

运行后在 `output/` 目录下生成：
* `output/master_voice.wav`：符合 -14 LUFS 广播标准的整轨母带音频（24kHz 32位单声道/立体声）；
* `output/timeline.json`：包含每句话精确开始时间、结束时间、朗读持续时间与文本内容的结构化清单。

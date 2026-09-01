# imageToAnimation

Windows 本地游戏素材批量制作工具。

当前目标：把多个游戏截图目录中的素材自动组合为拼接图片，或使用 FFmpeg 生成带随机转场的短视频。

## 当前功能

- 3 张 / 4 张图片模式切换
- 最多 4 个素材目录
- 每个目录各取 1 张 / 所有启用目录混合随机 / 指定单目录抽取
- 洗牌轮播：尽量把素材全部使用一遍后再重新随机
- 画布比例：9:16、3:4、16:9、自定义
- 图片模式：按比例上下拼接、接缝虚化、批量 JPG 输出
- 视频模式：每张随机显示 3–5 秒、随机 FFmpeg `xfade` 转场、批量 H.264 MP4 输出
- 自动保存上次使用的目录和参数
- 本地 `bin/ffmpeg.exe` 优先，不要求配置系统环境变量

## 技术栈

- Python 3.10+
- CustomTkinter
- Pillow
- FFmpeg / ffprobe
- PyInstaller

## 快速开始

```bat
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File scripts\download_ffmpeg.ps1
python app.py
```

也可以运行：

```bat
run.bat
```

## 打包 EXE

```bat
build.bat
```

默认使用 PyInstaller `onedir` 模式，生成目录：

```text
dist\ImageToAnimation\
├─ ImageToAnimation.exe
└─ bin\
   ├─ ffmpeg.exe
   └─ ffprobe.exe
```

> FFmpeg 二进制不直接提交到仓库。`scripts/download_ffmpeg.ps1` 会下载 Windows essentials build 并放到 `bin/`。

详细功能状态见 [`docs/ROADMAP.md`](docs/ROADMAP.md)。

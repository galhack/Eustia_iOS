# 秽翼的尤斯蒂娅 · Apple 平台移植

把 August《秽翼的尤斯蒂娅》（Aiyoku no Eustia，BGI / Ethornell 引擎 1.520）原生移植到
**iPhone、iPad、Mac 与 Apple Vision Pro**。日文原版与已打汉化补丁的游戏目录都可以游玩
（汉化文本按 GBK 解码，界面按简体中文显示）。

> **本仓库不包含任何游戏内容。** 游戏的可执行文件、剧本、图片、音乐、语音、影片与汉化补丁
> 都不在这里，也不会被打包进应用或安装包。你需要自行购买正版游戏，并把自己游戏目录里的
> 文件导入到设备上。

**验证状态**：Mac 应用已实际运行到标题、冷开场、正文与存档/读档；iPhone/iPad/visionOS
模拟器均通过。**iPhone 16 Pro Max 真机已用 Sideloadly 安装并验证**（标题、正文、快速存档、
重启后快速读档）；iPad 与 Vision Pro 真机需用同样方式侧载/在 Xcode 里签名安装，步骤见下。
详细记录见 [docs/VALIDATION.md](docs/VALIDATION.md)。

---

## 它是怎么工作的

- 引擎：开源的 BGI 重实现 [OpenBGI](https://github.com/Cytlan/openbgi)（C99，GPL-2.0）。
  本作为其新增了游戏所用的引擎版本 **1.520** 配置。原版 `BGI.exe` 带有 Alpha-ROM 类
  DRM 加壳，静态无法取得指令表，因此 1.520 采用同年的 **1.529** 指令集行作为代理，
  并用本作原版与汉化版的全部程序实际验证（逆向与验证记录见 `tools/re/`、`docs/`）。
- Apple 后端（`engine/openbgi/src/os/apple/`）：引擎在独立线程运行；Metal 呈现；
  Core Text 渲染字形（中文优先使用苹方 / 冬青黑体等系统字体）；AudioToolbox 输出声音；
  pl_mpeg 解码 MPEG-1 影片；存档与游戏数据分离保存。
- 汉化：本作汉化版的剧本是 **GBK** 编码。引擎检测到 GBK 文本后自动按 GBK 解码，
  因此不需要在电脑上做任何预处理，也不需要在设备上解包补丁。
- 应用外壳：SwiftUI + UIKit，一个工程同时构建 iOS/iPadOS、Mac（Mac Catalyst）与
  visionOS 原生版本。

---

## 你需要准备

1. 已购买的正版《秽翼的尤斯蒂娅》安装目录，其中应包含
   `BGI.exe`、`system.arc`、`sysprg.arc`、`sysgrp.arc`、`data01000.arc` … `data050xx.arc`、
   `BGI.gdb`、`BGI.hvl`（以及 `UserData` 等）。
2. （可选）已打汉化补丁的同目录文件：汉化版的剧本 / 系统文件会替换到这些 `.arc` 中，
   文本为 GBK；本移植会自动识别。
3. 一台装有 **Xcode** 的 Mac；侧载 iPhone / iPad 也可以用 **Sideloadly**。
4. 一个 Apple ID（免费账户签名 7 天有效，需定期重装；付费开发者账户为 1 年）。

设备空间：游戏数据约 4.6 GB。应用本身不含数据，安装包只有约 1 MB。

---

## 构建

### 生成 Xcode 工程

```sh
git clone <本仓库>
cd eustia
EUSTIA_TEAM=<你的 Team ID> tools/apple/gen_project.sh
open app/Eustia.xcodeproj
```

Team ID 可在 Xcode › Settings › Accounts 中查看（免费账户的个人团队也有 Team ID）。
也可以把它写进 `app/.team`（单行，不会提交到 git），之后直接运行
`tools/apple/gen_project.sh`。脚本会在本机 `build/tools/` 中准备 XcodeGen，工程不依赖
任何第三方库或 Metal 工具链。

### Mac 版

```sh
tools/apple/build_mac.sh          # 生成 build/Eustia-mac.zip（本机签名，不含游戏数据）
```

解压后把 `Eustia.app` 拖到「应用程序」。首次打开如被系统拦截，请右键 › 打开
（该应用未经公证）。也可以在 Xcode 中选择 "My Mac (Mac Catalyst)" 直接运行。
Mac 版无需 Apple ID。

启动后点「选择游戏目录…」，指向电脑上的游戏安装目录即可，**不需要复制数据**；选择会被记住。
存档保存在 `~/Library/Application Support/Eustia/`。

### 安装到 iPhone / iPad

**用 Xcode**：用数据线或同一局域网把设备与 Mac 配对，在 Xcode 顶部选择设备，点击 Run（▶）。
首次需要在设备上开启「开发者模式」，并在 设置 › 通用 › VPN 与设备管理 中信任你的开发者证书。

**用 Sideloadly**：

```sh
tools/apple/build_ipa.sh ios      # 生成 build/Eustia-ios.ipa（不含任何游戏数据，约 1 MB）
tools/apple/build_ipa.sh visionos # 生成 build/Eustia-visionos.ipa（原生 visionOS）
tools/apple/verify_all.sh         # 三种目标 Debug 构建 + 全部打包（开发者用）
```

在 Sideloadly 中选择该 IPA、你的设备和 Apple ID，点击 Start。

> 免费 Apple ID 每台设备最多同时保留 3 个侧载应用；更新时用同一个 Bundle ID 覆盖安装，
> 不要先卸载，这样可以保留已导入的数据与存档。

### Apple Vision Pro

本项目使用原生 visionOS 目标。在 Xcode 中把 Vision Pro 与 Mac 配对（保持头显解锁并开启
开发者模式），在工程的 Signing & Capabilities 中选择自己的 Team，选择已配对的
Vision Pro 为运行目标，点击 Run。安装后按下面的方法导入游戏文件。

---

## 导入游戏数据

应用第一次打开时会提示「尚未找到游戏文件」。把**整个游戏目录**放进应用即可，目录名随意。

| 设备 | 推荐方式 |
|---|---|
| iPhone / iPad | 数据线连接 Mac → 访达 › 选中设备 › **文件** › 「秽翼的尤斯蒂娅」→ 把游戏目录拖进去 |
| Vision Pro | 用隔空投送把游戏目录发到 Vision Pro，保存到「文件 › 我的 Apple Vision Pro › 秽翼的尤斯蒂娅」；或用下面的局域网传输 |
| 任意设备 | 局域网传输：在应用里打开「局域网接收游戏文件」，记下地址和配对码，在 Mac 上运行 `python3 tools/push_data.py --host <地址> --code <配对码> /path/to/游戏目录` |
| Mac | 启动器里点「选择游戏目录…」，不需要复制 |

传输脚本只发送需要的文件（`.arc` 封包、`BGI.gdb`、`BGI.hvl` 等），设备上已有且大小相同的
文件会跳过；中断后重新运行即可续传。

---

## 开始游戏

在启动页确认已检测到游戏目录，点「开始游戏」。汉化版会自动以简体中文运行；
原版日文目录则使用 Shift-JIS 文本。

> 原版与汉化版的存档不通用（与原补丁说明一致）。本移植把日文版与汉化版都当作
> 「同一款游戏」处理，存档目录相同；如果你同时保留两份数据，请只使用一份，
> 或分别放在不同设备/容器里。

### 操作方式

| 输入 | 对应 |
|---|---|
| 轻点 | 鼠标左键（推进文字、选择） |
| 双指轻点 | 鼠标右键（游戏菜单 / 隐藏文字框） |
| 上下滑动 | 鼠标滚轮（向下滑 = 打开回想） |
| 长按 | 按住 Ctrl（快进），松手停止 |
| Mac / iPad 鼠标与触控板 | 与 PC 版相同：按下、拖动、左右键、滚轮 |
| 硬件键盘 | Enter、空格、Esc、方向键、Ctrl（按住快进）等 |
| 游戏手柄 | 左摇杆移动指针，A = 左键，B = 右键，RT = 快进，十字键上/下 = 滚轮 |
| Vision Pro | 注视 + 捏合 = 轻点；其余同触控 |

---

## 存档

- 存档与游戏数据分开保存：iPhone / iPad / Vision Pro 在 Application Support，Mac 在
  `~/Library/Application Support/Eustia/`。
- 首次启动时会把游戏目录中的 `BGI.gdb`（全局设定、已读记录、CG 收集）复制一份作为起点，
  电脑上的进度因此可以带过来。
- 删除应用会同时删除存档。iPhone / iPad 可在访达中备份应用数据。

---

## 已知限制

- 免费 Apple ID 签名 7 天后过期，需要重新安装（不会删除已导入的数据和存档）。
- 游戏数据约 4.6 GB，首次导入耗时较长；iPad / iPhone 请预留足够空间。
- 汉化补丁的文本由汉化组提供，本移植只负责正确解码与显示；补丁本身的翻译内容与权利归汉化组。
- Mac 版为 Mac Catalyst 构建，未做公证。
- 全新启动时标题菜单可能不显示 CONTINUE/DATA LOAD（存档存在时）；进入游戏后用
  LOAD 可以正常读档。这是已知行为差异，详见 `docs/VALIDATION.md`。
- 极少数原始日文错误提示在中文模式下可能显示为乱码；正常剧情不受影响。
- 8 个 MPEG-1 影片已验证解出画面，但未逐部完整播放到片尾。

---

## 开发与调试

| 路径 | 内容 |
|---|---|
| `engine/openbgi/` | OpenBGI 引擎及本项目修改（上游 commit 见 `engine/UPSTREAM_COMMIT`） |
| `engine/openbgi/src/os/apple/` | Apple 平台后端 |
| `app/` | XcodeGen 工程定义与 Swift 外壳 |
| `tools/re/` | 原版 `BGI.exe` / 脚本分析脚本（1.520 指令集代理与缺失指令恢复） |
| `tools/data/` | PackFile / ARC20 封包与资源格式检查工具 |
| `tools/apple/` | 工程生成、IPA / Mac 打包（`verify_all.sh` 一次全量构建） |
| `tools/check/` | 图像解码检查等工具 |
| `docs/VALIDATION.md` | 验证记录、覆盖边界、复现命令 |
| `docs/RE-1520.md` | 原版 `BGI.exe` / 数据的逆向报告 |
| `engine/PORTING-1520.md` | 引擎移植说明（指令集代理、布局、GBK、已知限制） |

在 Mac 上不用模拟器即可运行同一套 Apple 后端：

```sh
cd engine/openbgi && make PLATFORM=apple CC=clang VORBIS=stb bin/openbgi-hosttest
bin/openbgi-hosttest /path/to/游戏目录 --chinese --save=/tmp/save --seconds=30 --shot=/tmp/title.png
```

---

## 许可

- 本项目代码（含引擎修改、Apple 后端、应用外壳）以 **GPL-2.0** 发布，见 `LICENSE`。
- 第三方组件（OpenBGI、pl_mpeg、stb_vorbis、参照 GARbro 的 CBG 算法）见
  `THIRD_PARTY_NOTICES.md`。
- 《秽翼的尤斯蒂娅》及其一切内容版权归 August 所有；中文补丁归其汉化组所有。
  本项目与上述权利人无关，仅供已购买正版的玩家在自己的设备上游玩。

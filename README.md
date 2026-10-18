# 秽翼的尤斯蒂娅 · iPhone / iPad / Mac 移植

把 August 的《秽翼的尤斯蒂娅》（Aiyoku no Eustia，BGI / Ethornell 引擎 1.520）移植到
**iPhone、iPad 与 Mac**。日文原版或已打汉化补丁的游戏目录都可以直接游玩（汉化文本按
GBK 解码，界面按简体中文显示）。

> **本仓库和 Release 不包含任何游戏内容。** 可执行文件、剧本、图片、音乐、语音、影片与
> 汉化补丁都不在这里，也不会被打包进应用或安装包。请自行购买正版游戏，并把你自己的
> 游戏目录导入设备。本项目仅供已购买正版的玩家个人使用，与 August 及汉化组无关。

本次发布范围：**iPhone / iPad（侧载安装）与 Mac（可选）**。

---

## 下载与安装（iPhone / iPad）

### 1. 下载 IPA

在 [Releases](https://github.com/galhack/Eustia_iOS/releases) 下载 `Eustia-ios.ipa`
（约 1 MB，不包含游戏数据）。

### 2. 用 Sideloadly 侧载

1. 在电脑上安装 [Sideloadly](https://sideloadly.io/)（Windows / macOS 均可）。
2. 用数据线连接 iPhone / iPad，解锁并在手机上点「信任」。
3. 打开 Sideloadly，把 `Eustia-ios.ipa` 拖进窗口，选择你的设备和 Apple ID。
4. 点 **Start**，等待出现 `Done.`。

> 免费 Apple ID 签名的应用 **7 天**后过期，到期后重新侧载即可（覆盖安装，不要先卸载，
> 否则应用内的游戏数据和存档会一起被删除）。免费账户在每台设备上最多同时保留 3 个
> 侧载应用。

### 3. 信任开发者证书

在设备上打开 **设置 › 通用 › VPN 与设备管理 › 开发者 App**，选择你的 Apple ID 并点
「信任」。iOS 16 及以上还需要在 **设置 › 隐私与安全性 › 开发者模式** 中开启开发者模式
（开启后设备会重启一次）。

### 4. 导入游戏数据

应用本身不包含游戏。第一次打开会提示「尚未找到游戏文件」，把**整个游戏目录**放进应用
容器即可（目录名随意，推荐 `Game`）：

| 方式 | 操作 |
|---|---|
| 访达文件共享（推荐） | 数据线连接 Mac → 访达 › 选中设备 › **文件** ›「秽翼的尤斯蒂娅」→ 把游戏目录拖进去 |
| 局域网传输 | 在应用启动页打开「局域网接收游戏文件」，记下地址与配对码，在 Mac 上运行 `python3 tools/push_data.py --host <地址> --code <配对码> /path/to/游戏目录` |

游戏数据约 **4.6 GB**，首次导入需要几分钟；请预留足够空间。应用只读取游戏目录，不会修改它。

### 5. 开始游戏

回到启动页确认已检测到游戏目录，点「开始游戏」。汉化版会自动以简体中文运行；原版日文
目录则使用 Shift-JIS 文本。

---

## 操作方式

| 输入 | 对应 |
|---|---|
| 轻点 | 鼠标左键（推进文字、选择） |
| 双指轻点 | 鼠标右键（游戏菜单 / 隐藏文字框） |
| 上下滑动 | 鼠标滚轮（向下滑 = 打开回想） |
| 长按 | 按住 Ctrl（快进），松手停止 |
| 鼠标 / 触控板 | 与 PC 版相同：按下、拖动、左右键、滚轮 |
| 硬件键盘 | Enter、空格、Esc、方向键、Ctrl（按住快进）等 |
| 游戏手柄 | 左摇杆移动指针，A = 左键，B = 右键，RT = 快进，十字键上/下 = 滚轮 |

---

## 存档

- 存档与游戏数据分开保存：iPhone / iPad 在应用容器的 `Application Support/Eustia/save`，
  Mac 在 `~/Library/Application Support/Eustia/`。
- 首次启动会把游戏目录中的 `BGI.gdb`（全局设定、已读记录、CG 收集）复制一份作为起点。
- 删除应用会同时删除存档；升级侧载时请使用相同 Bundle ID 覆盖安装。

---

## Mac 版（可选）

Release 同时提供 `Eustia-mac.zip`。解压后把 `Eustia.app` 拖到「应用程序」，首次打开如被
系统拦截请右键 › 打开（应用未公证）。启动后点「选择游戏目录…」指向电脑上的游戏目录即可，
**不需要复制数据**；选择会被记住，存档在 `~/Library/Application Support/Eustia/`。

也可以自行构建：

```sh
tools/apple/build_mac.sh
```

---

## 从源码构建（开发者）

需要 macOS、Xcode 27 和 XcodeGen（脚本会在 `build/tools/` 中准备，不污染系统）。

```sh
git clone https://github.com/galhack/Eustia_iOS.git
cd Eustia_iOS
EUSTIA_TEAM=<你的 Team ID> tools/apple/gen_project.sh
open app/Eustia.xcodeproj
```

构建未签名 IPA（交给 Sideloadly 签名）：

```sh
tools/apple/build_ipa.sh ios      # build/Eustia-ios.ipa
```

Mac 版：

```sh
tools/apple/build_mac.sh          # build/Eustia-mac.zip
```

在 Mac 上直接运行 Apple 后端（无需模拟器）：

```sh
cd engine/openbgi && make PLATFORM=apple CC=clang VORBIS=stb bin/openbgi-hosttest
bin/openbgi-hosttest /path/to/游戏目录 --chinese --save=/tmp/save --seconds=30 --shot=/tmp/title.png
```

仓库结构：

| 路径 | 内容 |
|---|---|
| `engine/openbgi/` | OpenBGI 引擎及本项目修改 |
| `engine/openbgi/src/os/apple/` | Apple 平台后端（Metal / CoreText / AudioToolbox / pl_mpeg） |
| `app/` | XcodeGen 工程定义与 Swift 外壳 |
| `tools/re/` | 原版 `BGI.exe` / 脚本分析脚本 |
| `tools/data/` | PackFile / ARC20 / 资源格式检查工具 |
| `tools/apple/` | 工程生成、IPA / Mac 打包 |
| `docs/VALIDATION.md` | 验证记录与覆盖边界 |
| `docs/RE-1520.md` | 原版 `BGI.exe` / 数据逆向报告 |
| `engine/PORTING-1520.md` | 引擎移植说明 |

---

## 已知限制

- 免费 Apple ID 签名 7 天后过期，需要重新侧载；覆盖安装不会删除数据与存档。
- 全新启动时标题菜单可能不显示 CONTINUE / DATA LOAD（存档存在时）；进入游戏后用 LOAD
  可以正常读档。这是已知行为差异。
- 极少数由原版程序弹出的日文错误提示在中文模式下可能显示为乱码；正常剧情不受影响。
- 8 个 MPEG-1 影片已验证解码与画面，但未逐部完整播放到片尾。
- Mac 版为 Mac Catalyst 构建，未做公证。
- iOS 侧载依赖 Sideloadly 等工具和你自己的 Apple ID；本项目不提供证书或账号。

---

## 许可与致谢

- 本项目代码（引擎修改、Apple 后端、应用外壳）以 **GPL-2.0** 发布，见 `LICENSE`。
- 第三方组件（OpenBGI、pl_mpeg、stb_vorbis、参照 GARbro 的 CBG 算法等）见
  `THIRD_PARTY_NOTICES.md`。
- 《秽翼的尤斯蒂娅》及其一切内容版权归 **August** 所有；中文补丁归其汉化组所有。
  本项目与上述权利人无关，仅供已购买正版的玩家在自己的设备上游玩。

**作者**：galhack · **联系**：galhack@protonmail.com · **协作**：DeepSeek

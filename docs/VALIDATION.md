# 验证记录与覆盖边界

本文件记录《秽翼的尤斯蒂娅》Apple 移植的验证结果、复现命令与尚未覆盖的部分。
所有截图都来自本仓库代码；仓库与安装包里**没有任何游戏内容**。截图本身包含游戏画面，
只保存在被 git 忽略的 `build/screenshots/` 里，不随仓库发布。

## 环境

- macOS + **Xcode 27.1**（iOS 27.0 / visionOS 27.0 SDK）。
- 构建：`tools/apple/verify_all.sh`（生成工程 → Mac Catalyst / iOS Simulator /
  visionOS Simulator Debug 构建 → 三个发布包）。
- 引擎：OpenBGI + Apple 后端；本作新增 `GEN_1_520`
  （1.529 指令集行 + 1.529 行为门限，`LAYOUT_C` 指针布局，64 MB 堆）。原版
  `BGI.exe` 带 Alpha-ROM 类加壳，无法静态导出指令表（见 [RE-1520.md](RE-1520.md)、
  `engine/PORTING-1520.md`）。
- 游戏数据：汉化补丁 V1.5 + 修正脚本 151007，剧本为 **GBK**；共 65 个封包 /
  4.6 GB，含 8 个 MPEG-1 影片。

## 已验证

### 1. 引擎无头宿主（macOS，与 app 相同的 Apple 后端）

```sh
cd engine/openbgi
make PLATFORM=apple CC=clang VORBIS=stb -j8 bin/openbgi-hosttest
BGI_TEST_TMP=/tmp ./bin/test_games
BGI_TEST_TMP=/tmp ./bin/test_scriptenc
make PLATFORM=apple CC=clang VORBIS=stb -j8 test   # 全部测试通过
bin/openbgi-hosttest GAME_DIR --chinese --save=/tmp/save --seconds=60 \
  --script="wait 20 click 640 330 wait 3 shot /tmp/title.png"
```

| 项目 | 结果 |
|---|---|
| 游戏识别 / 产品名反篡改 / 无 games.json 启动 | 通过（`bgi: engine profile 1.520 selected`） |
| 标题画面（1280×720） | 通过（`build/screenshots/mac-title.png`） |
| 冷开场 → START → 正文 | 通过（`build/screenshots/mac-story.png`、`dialogue.png`） |
| GBK 中文解码、换行、角色名框、立绘、背景 | 通过（`dialogue.png`） |
| 系统设置（分页、预览窗） | 通过（`/tmp/cfgB-2.png`，LAYOUT_B/C 逐字节相同） |
| 存档（SAVE → 槽位 → 确认）与跨进程读档（LOAD） | 通过：`UserData/AiyokunoEustia000.sud` 写入，重开进程后 LOAD 恢复到同一句（`save-menu.png`、`load-resumed.png`） |
| 音频（BW/Ogg Vorbis） | `BGI_SND_DEBUG=1` 显示 BGM 声道加载/循环，无错误 |
| 影片（MPEG-1，`data02840.arc`） | 通过：`--movie=data02840.arc:movie.mpg` 解出 OP 画面（`movie-frame.png`） |
| 2.5 分钟连续点击 | 无 undefined / not implemented / 报错 |
| 退出码 / 窗口尺寸 | 正常；游戏原生 1280×720（`ipl` 的 display mode 6） |

### 2. Mac 应用（Mac Catalyst）

`build/Eustia-mac.app`，通过 `Info.plist` 的 `LSEnvironment` 注入
`EUSTIA_GAME_DIR` / `EUSTIA_AUTOSTART` / `EUSTIA_SCRIPT` 自动化运行：

- 启动器检测游戏目录、自动识别 GBK；
- 引擎以 1.520 profile 启动，标题与冷开场中文文本经 Metal 正常渲染
  （`build/screenshots/mac-title.png`、`mac-story.png`）；
- 存档目录初始化（`~/Library/Application Support/Eustia/save`，`BGI.gdb` 播种）。

### 3. 模拟器（无需签名，完整数据）

| 目标 | 项目 | 结果 |
|---|---|---|
| iPhone 18 Pro Max，iOS 27 | 启动器检测数据 → 引擎 → 标题画面；冷开场中文文本 | 通过（`iphone-sim-title.png`、`iphone-sim-story-device.png`） |
| iPad Pro 13" (M5)，iOS 27 | 同上，1280×720 画面自适应 | 通过（`ipad-sim-title.png`、`ipad-sim-device.png`） |
| Apple Vision Pro，visionOS 27 | 原生 visionOS 窗口、标题画面（含版权 WARNING 页） | 通过（`vision-sim-title2.png`、`vision-sim-device2.png`） |

模拟器运行时通过 `SIMCTL_CHILD_EUSTIA_GAME_DIR` 指向 `/tmp` 下的完整数据副本；
应用只读取，不写入游戏目录。

### 4. 数据格式普查（`tools/data/asset_survey.py`）

| 项目 | 结果 |
|---|---|
| PackFile / ARC20 封包 | 65 个全部可读 |
| CompressedBG 图片 | 5163 张，全部 version 1，解码 0 失败 |
| BW 音频 | 38539 个，全部 Ogg Vorbis |
| 影片 | 8 个 MPEG-1（1280×720/30fps + MP2），全部在 `data02840.arc` |
| 编译脚本（BCS） | 205 个 |
| 0xFF 用户指令 | 未使用 |

## 真机状态

### iPhone 16 Pro Max（已真机验证）

- 用 **Sideloadly**（保存的 Apple ID，免费账号）签名安装 `build/Eustia-ios.ipa`；
  安装后 Bundle ID 被 Sideloadly 追加了一次 Team ID（`org.local.eustia.HM588ACCT5.HM588ACCT5`），
  不影响使用。
- 通过 `devicectl` 把 4.2 GB 游戏数据推送进应用容器 `Documents/Game`（app 只读）。
- 实测结果：
  - 启动、引擎以 1.520 profile 启动、标题画面（`build/screenshots/iphone-real-device.png`）；
  - START → 冷开场 → 正文，中文文本/立绘/背景/文本框菜单正常
    （`iphone-real-dialogue.png`）；
  - 快速存档（Q-SAVE → 是）写入 `AiyokunoEustia152.sud`（557 KB）；
  - 结束进程后重新启动 → Q-LOAD → 是，恢复到存档那一句
    （`iphone-real-loadprompt.png`、`iphone-real-loaded.png`）；
  - 真机全程无 undefined / not implemented / 报错。

### 其他真机

| 设备 | 状态 |
|---|---|
| iPad Pro（M5） | 工程与 IPA 就绪、iPad 模拟器通过；真机需用同一 IPA 在 Sideloadly 侧载并推送数据（步骤见 README），本轮未接入 USB，未做真机复测。 |
| Apple Vision Pro（第一代） | 原生 visionOS 目标与未签名 IPA 已生成、visionOS 模拟器通过；真机需在 Xcode 中选 Team 后 Run（或后续用支持 visionOS 的侧载方式）。 |

> 真机安装需要玩家自己的 Apple ID 签名，这是 Apple 的限制；本仓库不包含任何证书、
> 描述文件或账号信息。

## 覆盖边界 / 已知限制

1. **引擎版本代理**：原版 `BGI.exe` 加壳，1.520 采用 1.529 指令集行作为代理；
   原版 + 汉化版全部 234,773 条指令所用指令都在该行内，仅 `A0 23`、`main 77`
   两个缺失指令被引用（已实现）。若发现未定义指令，引擎会明确报错。
2. **标题菜单 CONTINUE**：全新进程启动时，即使存档存在，标题也只显示
   START/CONFIGURATION/EXIT；同一进程内保存并回到标题后才会出现
   CONTINUE/DATA LOAD。游戏内 LOAD 不受影响。这是已知行为差异（引擎启动时未刷新
   存档标记），不影响读档本身。
3. **字体**：Windows 汉化通过 Detours 强制 GDI 字体“黑体”；本移植用 CoreText 的
   CJK 回退（PingFang SC / STHeiti SC / Hiragino Sans GB），字形/行宽可能细微不同。
   正文换行使用引擎的 GBK 感知禁则处理。
4. **错误提示框中的日文**：极少数由 `sysprg` 程序弹出的原始日文提示（例如缺文件
   错误）在 GBK 模式下可能显示为乱码；正常剧情文本不受影响。
5. **影片**：8 个 MPEG-1 影片已验证解码与首帧画面；未逐部完整播放到片尾。
6. **Mac**：Mac Catalyst 构建，未公证；首次打开需右键 › 打开。
7. **侧载**：免费 Apple ID 签名 7 天有效；更新时用同一 Bundle ID 覆盖安装以保留数据。
8. **原版日文**：启动器按脚本编码自动区分 GBK / Shift-JIS；原版与汉化版存档不通用。

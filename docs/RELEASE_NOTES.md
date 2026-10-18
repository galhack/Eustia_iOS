# Eustia_iOS v0.1.0

《秽翼的尤斯蒂娅》（Aiyoku no Eustia）的 iPhone / iPad / Mac 移植首个版本。

- **作者**：galhack
- **联系**：galhack@protonmail.com
- **协作**：DeepSeek
- **支持**：iPhone（iOS 17+）、iPad（iPadOS 17+）、Mac（Mac Catalyst 14+）
- **不包含**：Vision Pro 版本（尚未调试，本次不发布）

## 安装（iPhone / iPad）

1. 下载本 Release 里的 `Eustia-ios.ipa`。
2. 用 [Sideloadly](https://sideloadly.io/) 连接设备、选择该 IPA 与你的 Apple ID，点 Start。
3. 在设备上：设置 › 通用 › VPN 与设备管理 › 开发者 App，信任你的证书；
   并在 设置 › 隐私与安全性 › 开发者模式 中开启开发者模式。
4. 打开应用，按提示用「访达 › 文件」或应用内「局域网接收游戏文件」导入自行购买的游戏目录
   （约 4.6 GB）。
5. 点「开始游戏」。

免费 Apple ID 签名 7 天有效，到期后用相同 Bundle ID 覆盖安装即可，数据和存档会保留。

## 资产

| 文件 | SHA-256 |
|---|---|
| `Eustia-ios.ipa` | `b04ea78313d45bdb79c1dc51809aca846368e83e54a3b79b1eeab37b6fa7d125` |
| `Eustia-mac.zip` | `cb252163aef16f168391e54bf03291c653429779a605c6b445e3eb3dc7e3f8ab` |

两个包都不包含任何游戏数据。

## 已知限制

- 免费签名 7 天过期；覆盖安装保留数据，卸载会删除存档。
- 全新启动时标题菜单可能不显示 CONTINUE / DATA LOAD；进入游戏后 LOAD 正常。
- 极少数原版日文错误提示在中文模式下可能乱码。
- 影片已验证解码与画面，但未逐部完整播放到片尾。
- Mac 版未公证，首次打开需右键 › 打开。

## 许可

本项目代码以 GPL-2.0 发布；游戏与汉化补丁的权利归各自权利人所有。请先购买正版游戏。

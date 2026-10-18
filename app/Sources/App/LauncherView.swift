import SwiftUI
import UniformTypeIdentifiers

/// The first screen: whether the game data is there, how its scripts are
/// encoded, and how to bring the files onto this device.
struct LauncherView: View {
    @EnvironmentObject private var model: AppModel
    @ObservedObject private var transfer = TransferServerObserver.shared
    @State private var showingPicker = false
    @State private var pickAction: PickAction = .choose

    private enum PickAction {
        case choose      // play where it is (Mac) / import a device folder
        case importCopy  // copy into the app's own folders
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                header
                statusCard
                if model.gameFolder != nil {
                    languageSection
                    startButton
                }
                importCard
                transferCard
                if let error = model.errorMessage {
                    Text(error).foregroundStyle(.red).textSelection(.enabled)
                }
                footer
            }
            .padding(.horizontal, 40)
            .padding(.vertical, 36)
            .frame(maxWidth: 900, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
        .onAppear {
            TransferServerObserver.shared.bind(model.transfer)
            model.refresh()
        }
        .fileImporter(isPresented: $showingPicker, allowedContentTypes: [.folder]) { result in
            guard case .success(let url) = result else { return }
            switch pickAction {
            case .choose: model.pickGameFolder(url)
            case .importCopy: model.importFolder(url)
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("秽翼的尤斯蒂娅").font(.largeTitle.bold())
            Text("Aiyoku no Eustia · Apple 平台移植").foregroundStyle(.secondary)
        }
    }

    // MARK: - game data

    private var statusCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 10) {
                if let folder = model.gameFolder {
                    Label("已找到游戏数据", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    Text(folder.path)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                        .textSelection(.enabled)
                    fileChecklist
                    if !model.missingFiles.isEmpty {
                        Label("缺少：\(model.missingFiles.joined(separator: "、"))",
                              systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.orange)
                        Text("游戏数据不完整，可能无法启动。请重新导入完整的游戏目录。")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else if model.archiveCount > 0 {
                        Text("共 \(model.archiveCount) 个 .arc 数据包").font(.footnote).foregroundStyle(.secondary)
                    }
                    Text(model.detectionNote).font(.footnote).foregroundStyle(.secondary)
                } else {
                    Label("尚未找到游戏数据", systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                    Text("请放入你自己购买的游戏数据目录（包含 system.arc、sysprg.arc、sysgrp.arc、data01000.arc）。")
                        .foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } label: {
            Text("游戏数据")
        }
    }

    private var fileChecklist: some View {
        VStack(alignment: .leading, spacing: 3) {
            ForEach(GamePaths.fileChecklist(in: model.gameFolder ?? URL(fileURLWithPath: "/"))) { item in
                HStack(spacing: 6) {
                    Image(systemName: item.present ? "checkmark.circle.fill" : "circle.dotted")
                        .foregroundStyle(item.present ? Color.green : Color.secondary)
                    Text(item.name).font(.system(.footnote, design: .monospaced))
                        .foregroundStyle(item.present ? Color.primary : Color.secondary)
                }
            }
        }
    }

    // MARK: - language and start

    private var languageSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Picker("脚本语言", selection: Binding(get: { model.language },
                                                 set: { model.selectLanguage($0) })) {
                ForEach(GameLanguage.allCases) { lang in
                    Text(lang.title).tag(lang)
                }
            }
            .pickerStyle(.segmented)
            Text("汉化版（GBK 文本）选「简体中文」；原版日文数据选「日本語」。选错会显示乱码。")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    private var startButton: some View {
        Button {
            model.start()
        } label: {
            Text("开始游戏").font(.title2.bold()).frame(maxWidth: .infinity).padding(.vertical, 8)
        }
        .buttonStyle(.borderedProminent)
        .disabled(!model.isComplete || model.importing)
    }

    // MARK: - importing

    private var importCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 12) {
                #if os(tvOS)
                Text("Apple TV 没有文件管理，请通过局域网从 Mac 发送游戏文件。")
                #elseif targetEnvironment(macCatalyst)
                Text("「选择游戏目录…」直接使用电脑上的游戏目录，不会复制文件；「从「文件」导入…」会把目录复制到 App 自己的存储中。")
                #elseif os(visionOS)
                Text("方式一：用隔空投送把整个游戏目录存到「文件」App，再点「从「文件」导入…」。")
                Text("方式二：在同一个 Wi-Fi 下用 Mac 运行 tools/push_data.py，通过局域网传输（见下方）。")
                #else
                Text("方式一：用数据线连接 Mac，在访达 › 设备 › 文件 中把整个游戏目录拖进本应用。")
                Text("方式二：先把游戏目录存到「文件」App，再点「从「文件」导入…」。")
                Text("方式三：在同一个 Wi-Fi 下用 Mac 运行 tools/push_data.py，通过局域网传输（见下方）。")
                #endif
                HStack(spacing: 12) {
                    #if !os(tvOS)
                    Button("选择游戏目录…") { pickAction = .choose; showingPicker = true }
                        .disabled(model.importing)
                    Button("从「文件」导入…") { pickAction = .importCopy; showingPicker = true }
                        .disabled(model.importing)
                    #endif
                    Button("重新检查") { model.refresh() }
                        .disabled(model.importing)
                }
                if model.importing {
                    VStack(alignment: .leading, spacing: 6) {
                        ProgressView()
                        Text(model.importStatus).font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } label: {
            Text(model.gameFolder == nil ? "导入游戏数据" : "更换游戏数据")
        }
    }

    // MARK: - local network transfer

    private var transferCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 12) {
                Toggle("局域网接收游戏文件（同一 Wi-Fi）", isOn: Binding(
                    get: { transfer.running },
                    set: { $0 ? model.transfer.start() : model.transfer.stop() }))
                if transfer.running {
                    Text("配对码：\(transfer.code)").font(.title3.monospacedDigit().bold())
                    let addresses = TransferServer.addresses()
                    if addresses.isEmpty {
                        Text("未检测到局域网地址，请确认设备已连接 Wi-Fi。").foregroundStyle(.orange)
                    }
                    ForEach(addresses, id: \.self) { ip in
                        VStack(alignment: .leading, spacing: 2) {
                            Text("在 Mac 上运行：").font(.footnote).foregroundStyle(.secondary)
                            Text("python3 tools/push_data.py --host \(ip) --code \(transfer.code) <游戏目录>")
                                .font(.system(.footnote, design: .monospaced))
                                .textSelection(.enabled)
                        }
                    }
                    if transfer.bytesReceived > 0 {
                        Text("已接收 \(ByteCountFormatter.string(fromByteCount: transfer.bytesReceived, countStyle: .file))")
                            .foregroundStyle(.secondary)
                    }
                    if !transfer.lastEvent.isEmpty {
                        Text(transfer.lastEvent).font(.footnote).foregroundStyle(.secondary)
                    }
                } else {
                    Text("开启后，在 Mac 上运行 tools/push_data.py，把游戏目录发送到本设备。")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } label: {
            Text("局域网传输")
        }
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: 4) {
            #if targetEnvironment(macCatalyst)
            Text("操作：鼠标与键盘同 PC 版 · 左键 = 确定 · 右键 = 菜单 · 滚轮 = 回想 · 按住 Control = 快进")
            #else
            Text("操作：轻点 = 左键 · 双指轻点 = 右键（菜单）· 上下滑动 = 滚轮（回想）· 长按 = 快进（Ctrl）")
            Text("也可连接键盘、鼠标、触控板或手柄，用法同 PC 版。")
            #endif
            Text("本应用不包含任何游戏内容与美术素材，游戏数据需由玩家自行购买。")
        }
        .font(.footnote)
        .foregroundStyle(.secondary)
    }
}

/// A titled panel (GroupBox is not available on tvOS).
struct Card<Content: View, Label: View>: View {
    @ViewBuilder var content: Content
    @ViewBuilder var label: Label

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            label.font(.headline)
            content
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color.white.opacity(0.08)))
    }
}

/// Republishes the transfer server's state for SwiftUI (the server itself
/// lives in the model and outlives the view).
final class TransferServerObserver: ObservableObject {
    static let shared = TransferServerObserver()

    @Published var running = false
    @Published var lastEvent = ""
    @Published var bytesReceived: Int64 = 0
    @Published var code = ""
    private var bound = false

    func bind(_ server: TransferServer) {
        guard !bound else { return }
        bound = true
        server.$running.receive(on: DispatchQueue.main).assign(to: &$running)
        server.$lastEvent.receive(on: DispatchQueue.main).assign(to: &$lastEvent)
        server.$bytesReceived.receive(on: DispatchQueue.main).assign(to: &$bytesReceived)
        server.$code.receive(on: DispatchQueue.main).assign(to: &$code)
    }
}

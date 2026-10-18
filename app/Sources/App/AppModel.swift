import Foundation
import SwiftUI

/// The launcher's state: where the game data is, how it is encoded, and the
/// running engine.
@MainActor
final class AppModel: ObservableObject {
    enum Phase: Equatable {
        case launcher
        case playing
        case ended(Int32)
    }

    @Published var phase: Phase = .launcher
    @Published var gameFolder: URL?
    @Published var isComplete = false
    @Published var missingFiles: [String] = []
    @Published var archiveCount = 0
    @Published var detectedEncoding: ScriptEncoding = .unknown
    @Published var language: GameLanguage = .chinese
    @Published var errorMessage: String?
    @Published var importing = false
    @Published var importStatus = ""

    let transfer = TransferServer()

    /// The detection reads a few megabytes of the script archive: run it off
    /// the main thread and drop the result if the folder changed meanwhile.
    private var detectionToken = 0
    /// True once the player has chosen a language for themselves; the
    /// automatic detection only sets the default.
    private var playerChoseLanguage = false

    init() {
        if let raw = UserDefaults.standard.string(forKey: "language"), let saved = GameLanguage(rawValue: raw) {
            language = saved
            playerChoseLanguage = true
        }
        transfer.onFileReceived = { [weak self] in
            Task { @MainActor in self?.refresh() }
        }
        refresh()
        DebugScript.redirectLogIfRequested()
        if let autostart = DebugScript.autostart {
            language = autostart
            playerChoseLanguage = true
            DispatchQueue.main.async { [weak self] in self?.start() }
        }
    }

    /// The automatic detection's summary shown by the launcher.
    var detectionNote: String {
        guard gameFolder != nil else { return "" }
        if let detected = detectedEncoding.language, detected == language {
            return "自动识别：\(detectedEncoding.title)"
        }
        switch detectedEncoding {
        case .gbk: return "自动识别：简体中文（GBK 汉化脚本）"
        case .shiftJIS: return "自动识别：日本語（Shift-JIS 原版脚本）"
        case .unknown: return "未能自动识别脚本编码，请按游戏版本选择语言。"
        }
    }

    /// Coming back to the front: files may have been copied in meanwhile.
    func refreshIfIdle() {
        if phase == .launcher { refresh() }
    }

    /// Look for the game data and its encoding again (after a copy, a network
    /// transfer, or the player pointing at another folder).
    func refresh() {
        let found = GamePaths.findGameFolder()
        gameFolder = found
        if let folder = found {
            isComplete = GamePaths.isCompleteGameFolder(folder)
            missingFiles = GamePaths.missingFiles(in: folder)
            archiveCount = GamePaths.archiveCount(in: folder)
            detectEncoding(of: folder)
        } else {
            isComplete = false
            missingFiles = GamePaths.requiredFiles
            archiveCount = 0
            detectedEncoding = .unknown
            detectionToken += 1
        }
    }

    private func detectEncoding(of folder: URL) {
        detectionToken += 1
        let token = detectionToken
        Task.detached(priority: .utility) {
            let encoding = ScriptInspector.detect(in: folder)
            await MainActor.run { [weak self] in
                guard let self, self.detectionToken == token else { return }
                self.detectedEncoding = encoding
                if !self.playerChoseLanguage, let detected = encoding.language {
                    self.language = detected
                }
            }
        }
    }

    /// The language picker: the player's choice wins over the detection from
    /// then on.
    func selectLanguage(_ newValue: GameLanguage) {
        language = newValue
        playerChoseLanguage = true
        UserDefaults.standard.set(newValue.rawValue, forKey: "language")
    }

    /// A folder chosen in the Files app / folder picker.  On the Mac the game
    /// plays where it is (`选择游戏目录…`); a device gets a copy in Documents.
    func pickGameFolder(_ url: URL) {
        #if targetEnvironment(macCatalyst)
        chooseGameFolderInPlace(url)
        #else
        importFolder(url)
        #endif
    }

    /// Play a folder where it is (Mac; the folder may be read-only).
    func chooseGameFolderInPlace(_ url: URL) {
        GamePaths.storeChosenGameFolder(url)
        refresh()
        if gameFolder == nil {
            errorMessage = "这个目录里没有找到游戏数据：需要 system.arc、sysprg.arc、sysgrp.arc 和 data01000.arc。"
        } else {
            errorMessage = nil
        }
    }

    /// Copy a folder into Documents.  Used by `从「文件」导入…` on every
    /// platform and by `选择游戏目录…` on a device.
    func importFolder(_ url: URL) {
        guard !importing else { return }
        importing = true
        importStatus = "正在复制「\(url.lastPathComponent)」…"
        errorMessage = nil
        Task.detached(priority: .userInitiated) {
            let scoped = url.startAccessingSecurityScopedResource()
            defer { if scoped { url.stopAccessingSecurityScopedResource() } }
            let result = Result { try GameImport.copy(url, into: GamePaths.importTarget) }
            await MainActor.run { [weak self] in
                guard let self else { return }
                self.importing = false
                self.importStatus = ""
                switch result {
                case .success(let target):
                    self.refresh()
                    if self.gameFolder == nil {
                        self.errorMessage = "已复制「\(target.lastPathComponent)」，但里面没有找到 game data（system.arc / sysprg.arc / sysgrp.arc / data01000.arc）。"
                    }
                case .failure(let error):
                    self.errorMessage = "导入失败：\(error.localizedDescription)"
                }
            }
        }
    }

    /// What the engine should do about the script encoding: the player's
    /// choice or the detection wins; with no hint at all, the engine samples
    /// the scripts itself (its automatic GBK/Shift-JIS detection).
    var engineScriptMode: EngineBridge.ScriptMode {
        if playerChoseLanguage || detectedEncoding.language != nil {
            return .forced(language)
        }
        return .auto
    }

    /// Start the engine on the found folder.  It cannot run twice in one
    /// process, so after it ends the app offers to quit (the player relaunches).
    func start() {
        guard let folder = gameFolder else {
            errorMessage = "还没有找到游戏数据，请先选择或导入游戏目录。"
            return
        }
        guard isComplete else {
            errorMessage = "游戏数据不完整（缺少：\(missingFiles.joined(separator: "、"))），请重新导入完整的游戏目录。"
            return
        }
        guard !importing else { return }
        errorMessage = nil
        EngineBridge.onEnd = { [weak self] code in
            self?.phase = .ended(code)
        }
        transfer.stop()
        if EngineBridge.start(gameFolder: folder, scriptMode: engineScriptMode) {
            phase = .playing
            DebugScript.runIfRequested()
        } else {
            errorMessage = "游戏引擎无法启动：请确认该目录中的游戏文件完整（system.arc、sysprg.arc、sysgrp.arc、data01000.arc）。"
            phase = .launcher
        }
    }

    /// Back to the launcher after the engine ended; the engine cannot run
    /// twice in one process, so the app quits when the player asks to play again.
    func quitApp() {
        exit(0)
    }
}

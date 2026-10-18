import Foundation

/// Where the port finds the player's game data and keeps its own files.
///
/// * iPhone, iPad, Vision Pro: the game folder is copied into the app's
///   Documents (Finder file sharing, the Files app, AirDrop) or received over
///   the local network; saves live in Application Support, out of the user's way.
/// * Mac: the player points at the folder where the game is installed
///   (`选择游戏目录…`) and nothing is copied.
///
/// The data folder of this game holds `system.arc`, `sysprg.arc`,
/// `sysgrp.arc` and `data01000.arc` (Buriko "PackFile" archives, GBK text in
/// the pre-applied Chinese patch).
enum GamePaths {
    static let fileManager = FileManager.default
    static let appName = "Eustia"

    /// The archives a complete data folder of this game has.
    static let requiredFiles = ["system.arc", "sysprg.arc", "sysgrp.arc", "data01000.arc"]
    /// The files that make a folder worth showing as a game folder even when
    /// the others are missing (the launcher then says what is missing).
    static let signatureFiles = ["system.arc", "data01000.arc"]

    static var documents: URL {
        fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }

    /// The user's Application Support folder (~/Library/Application Support on
    /// the Mac, the app container's on a device).
    static var applicationSupport: URL {
        let url = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? fileManager.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    /// Where the engine keeps `UserData\` and `BGI.gdb`:
    /// `Application Support/Eustia/save`.  On the first run the engine seeds it
    /// with the game folder's own `BGI.gdb` (settings and read marks), so the
    /// game data itself is never written to.
    static var saves: URL {
        let url = applicationSupport.appendingPathComponent("Eustia/save", isDirectory: true)
        try? fileManager.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    static var caches: URL {
        fileManager.urls(for: .cachesDirectory, in: .userDomainMask)[0]
    }

    /// Where the debug log and screenshots of an unattended run go.
    static var debugDirectory: URL {
        #if os(tvOS)
        caches.appendingPathComponent("Debug", isDirectory: true)
        #elseif targetEnvironment(macCatalyst)
        applicationSupport.appendingPathComponent("Eustia/Debug", isDirectory: true)
        #else
        documents.appendingPathComponent("Debug", isDirectory: true)
        #endif
    }

    /// The folder network transfers are written to, inside the app.
    static var transferTarget: URL {
        #if os(tvOS)
        let url = caches.appendingPathComponent("Game", isDirectory: true)
        #elseif targetEnvironment(macCatalyst)
        let url = applicationSupport.appendingPathComponent("Eustia/Game", isDirectory: true)
        #else
        let url = documents.appendingPathComponent("Game", isDirectory: true)
        #endif
        try? fileManager.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    /// Where `从「文件」导入…` puts a copy of the folder: Documents on a
    /// device (visible in the Files app), the app's own folder on the Mac
    /// (the Mac's Documents belong to the user).
    static var importTarget: URL {
        #if targetEnvironment(macCatalyst)
        transferTarget
        #else
        documents
        #endif
    }

    // MARK: - the folder the player chose (Mac, or an in-place import)

    private static let chosenPathKey = "gameFolderPath"
    private static let bookmarkKey = "gameFolderBookmark"
    /// The resolved folder and its held security-scoped access (one per run).
    private static var resolvedChosenFolder: URL?

    /// The folder picked last time, resolved from its bookmark (a Files-app
    /// folder on a device) or from the remembered path (Mac).
    static var chosenGameFolder: URL? {
        if let resolved = resolvedChosenFolder { return resolved }
        let defaults = UserDefaults.standard
        if let data = defaults.data(forKey: bookmarkKey) {
            var stale = false
            if let url = try? URL(resolvingBookmarkData: data, options: [.withoutUI],
                                  relativeTo: nil, bookmarkDataIsStale: &stale) {
                _ = url.startAccessingSecurityScopedResource()
                if stale { storeChosenGameFolder(url) }
                resolvedChosenFolder = url
                return url
            }
        }
        if let path = defaults.string(forKey: chosenPathKey) {
            let url = URL(fileURLWithPath: path, isDirectory: true)
            resolvedChosenFolder = url
            return url
        }
        return nil
    }

    /// Remember a folder: together with a security-scoped bookmark, so a
    /// Files-app folder that was not copied can be read again after a relaunch.
    static func storeChosenGameFolder(_ url: URL) {
        resolvedChosenFolder = url
        let defaults = UserDefaults.standard
        defaults.set(url.path, forKey: chosenPathKey)
        var options: URL.BookmarkCreationOptions = []
        #if targetEnvironment(macCatalyst)
        options.insert(.withSecurityScope)
        #endif
        if let data = try? url.bookmarkData(options: options, includingResourceValuesForKeys: nil, relativeTo: nil) {
            defaults.set(data, forKey: bookmarkKey)
        } else {
            defaults.removeObject(forKey: bookmarkKey)
        }
    }

    // MARK: - finding the game

    /// The game folder: one the player picked, a debug override, or a folder
    /// under Documents (the user may drop the game folder, or its `data`
    /// folder, anywhere in there, e.g. Documents/Game or a folder of the same
    /// name as the game).
    static func findGameFolder() -> URL? {
        if let env = ProcessInfo.processInfo.environment["EUSTIA_GAME_DIR"], !env.isEmpty {
            let url = URL(fileURLWithPath: env, isDirectory: true)
            if looksLikeGameFolder(url) { return url }
        }
        if let chosen = chosenGameFolder {
            if looksLikeGameFolder(chosen) { return chosen }
            // The player picked the install folder that contains the data folder.
            if let found = search(chosen, depth: 2, where: looksLikeGameFolder) { return found }
        }
        var roots: [URL] = []
        #if os(tvOS)
        roots = [transferTarget]
        #elseif targetEnvironment(macCatalyst)
        // The Mac's Documents belong to the user: only the app's own folders
        // and the folder the player pointed at are searched.
        roots = [transferTarget]
        #else
        roots = [documents, transferTarget]
        #endif
        for root in roots {
            if looksLikeGameFolder(root) { return root }
            if let found = search(root, depth: 3, where: looksLikeGameFolder) { return found }
        }
        return nil
    }

    /// A folder that holds the game's archives (a folder with only the
    /// signature files is still reported, so the launcher can say what is
    /// missing).
    static func looksLikeGameFolder(_ url: URL) -> Bool {
        var isDir: ObjCBool = false
        guard fileManager.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue else { return false }
        return signatureFiles.allSatisfy { fileExists(named: $0, in: url) }
    }

    /// The four required archives, present or not, in the order shown.
    static func fileChecklist(in folder: URL) -> [GameFile] {
        requiredFiles.map { GameFile(name: $0, present: fileExists(named: $0, in: folder)) }
    }

    static func missingFiles(in folder: URL) -> [String] {
        requiredFiles.filter { !fileExists(named: $0, in: folder) }
    }

    static func isCompleteGameFolder(_ folder: URL) -> Bool {
        missingFiles(in: folder).isEmpty
    }

    /// The `.arc` archives in the folder (the game ships a few dozen).
    static func archiveCount(in folder: URL) -> Int {
        let names = (try? fileManager.contentsOfDirectory(atPath: folder.path)) ?? []
        return names.filter { $0.lowercased().hasSuffix(".arc") }.count
    }

    private static func search(_ dir: URL, depth: Int, where match: (URL) -> Bool) -> URL? {
        let children = (try? fileManager.contentsOfDirectory(
            at: dir, includingPropertiesForKeys: [.isDirectoryKey], options: [.skipsHiddenFiles])) ?? []
        let sorted = children.sorted {
            $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending
        }
        for child in sorted {
            let isDir = (try? child.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) ?? false
            guard isDir else { continue }
            if match(child) { return child }
            if depth > 1, let found = search(child, depth: depth - 1, where: match) { return found }
        }
        return nil
    }

    /// The file of that name in the folder, the case of the name aside (the
    /// game was made for a case-insensitive file system).
    static func file(named name: String, in folder: URL) -> URL? {
        let direct = folder.appendingPathComponent(name)
        if fileManager.fileExists(atPath: direct.path) { return direct }
        let entries = (try? fileManager.contentsOfDirectory(atPath: folder.path)) ?? []
        if let match = entries.first(where: { $0.caseInsensitiveCompare(name) == .orderedSame }) {
            return folder.appendingPathComponent(match)
        }
        return nil
    }

    static func fileExists(named name: String, in folder: URL) -> Bool {
        file(named: name, in: folder) != nil
    }
}

/// One of the archives the game data folder must hold.
struct GameFile: Identifiable {
    let name: String
    let present: Bool
    var id: String { name }
}

/// The script text encoding of the copy the player has: this port targets the
/// pre-applied Simplified-Chinese patch (GBK), the original release is
/// Shift-JIS.
enum GameLanguage: String, CaseIterable, Identifiable {    case chinese = "zh"
    case japanese = "ja"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .chinese: return "简体中文（汉化）"
        case .japanese: return "日本語（原版）"
        }
    }

    var detail: String {
        switch self {
        case .chinese: return "GBK 脚本"
        case .japanese: return "Shift-JIS 脚本"
        }
    }

    var isChinese: Bool { self == .chinese }
}

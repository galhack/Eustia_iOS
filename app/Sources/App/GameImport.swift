import Foundation

/// Copies a game folder picked in the Files app (or a Mac folder the player
/// wants inside the app) into Documents.
///
/// The copy is published in one step: it is first made in a hidden staging
/// folder inside Documents and only renamed to its final name when complete,
/// so a cancelled or failed import never leaves a half-copied game folder
/// behind, and an existing installation is never deleted or overwritten.
enum GameImport {
    enum ImportError: LocalizedError {
        case alreadyExists
        case notAFolder

        var errorDescription: String? {
            switch self {
            case .alreadyExists:
                return "「文件」里已有同名游戏目录。请先重命名新目录，或删除旧目录后再导入。"
            case .notAFolder:
                return "请选择整个游戏目录（里面包含 system.arc、sysprg.arc 等文件），而不是单个文件。"
            }
        }
    }

    /// Copy `source` into `documents` as a sibling folder of the same name.
    /// Returns the folder's new location.
    @discardableResult
    static func copy(_ source: URL, into documents: URL) throws -> URL {
        let fm = FileManager.default
        var isDir: ObjCBool = false
        guard fm.fileExists(atPath: source.path, isDirectory: &isDir), isDir.boolValue else {
            throw ImportError.notAFolder
        }
        let target = documents.appendingPathComponent(source.lastPathComponent, isDirectory: true)
        if source.resolvingSymlinksInPath().standardizedFileURL == target.resolvingSymlinksInPath().standardizedFileURL {
            return target
        }
        guard !fm.fileExists(atPath: target.path) else { throw ImportError.alreadyExists }
        let staging = documents.appendingPathComponent(".import-\(UUID().uuidString)", isDirectory: true)
        defer {
            if fm.fileExists(atPath: staging.path) {
                do { try fm.removeItem(at: staging) }
                catch { NSLog("Eustia: import staging cleanup failed: %@", error.localizedDescription) }
            }
        }
        try fm.copyItem(at: source, to: staging)
        try fm.moveItem(at: staging, to: target)
        return target
    }
}

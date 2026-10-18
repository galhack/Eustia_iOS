import Foundation

#if canImport(UIKit)
import UIKit
#endif

/// The Swift side of engine/openbgi/inc/bgi/apple_host.h: starting the engine
/// thread and answering what it asks the application.
///
/// The engine detects the game by the archives in `gameFolder` (there is no
/// `games.json` written into the player's data: the game folder may be
/// read-only).  The audio, font and window back ends are the engine's own
/// (os/apple/); the only switch the shell sets is the script text encoding.
enum EngineBridge {
    /// Called on the main thread when the engine has returned (the player
    /// chose to quit, or it failed to start its game).
    static var onEnd: ((Int32) -> Void)?

    /// Shows a message box for the engine and returns the button chosen;
    /// installed by the game screen, called on the main thread.
    static var presentMessageBox: ((String, String, UInt32, @escaping (Int32) -> Void) -> Void)?

    /// Extra command line for Engine_Main, for diagnostics; normally none
    /// (the engine's own game detection and the defaults decide).
    static var engineArguments: String? {
        ProcessInfo.processInfo.environment["EUSTIA_ENGINE_ARGS"]
    }

    /// How the engine should decode the script text (apple_host.h).
    enum ScriptMode {
        /// Let the engine sample data01000.arc itself (APPLE_HOST_ENCODING_AUTO).
        case auto
        /// Decode as the given language's encoding (GBK or Shift-JIS).
        case forced(GameLanguage)

        var scriptEncoding: Int32 {
            switch self {
            case .auto: return 0   // APPLE_HOST_ENCODING_AUTO
            case .forced(.chinese): return 2   // APPLE_HOST_ENCODING_GBK
            case .forced(.japanese): return 1  // APPLE_HOST_ENCODING_SJIS
            }
        }

        var chinese: Int32 {
            if case .forced(.chinese) = self { return 1 }
            return 0
        }
    }

    /// Start the engine on its game folder.  Saves and `BGI.gdb` go to
    /// Application Support/Eustia/save; the engine seeds `BGI.gdb` from the
    /// game folder on the first run.  No overlay, font or patch executable is
    /// needed for this game: the Chinese patch is already applied to the data.
    static func start(gameFolder: URL, scriptMode: ScriptMode) -> Bool {
        AppleHost_SetEndHandler { code in
            DispatchQueue.main.async { EngineBridge.onEnd?(code) }
        }
        AppleHost_SetMessageBoxHandler { text, caption, flags in
            EngineBridge.askOnMainThread(text: text.map { String(cString: $0) } ?? "",
                                         caption: caption.map { String(cString: $0) } ?? "",
                                         flags: flags)
        }
        let saves = GamePaths.saves
        let args = engineArguments
        return gameFolder.path.withCString { game in
            saves.path.withCString { save in
                withOptionalCString(args) { engineArgs in
                    var cfg = AppleHostConfig_t(gameDir: game,
                                                overlayDir: nil,
                                                saveDir: save,
                                                fontFile: nil,
                                                chinese: scriptMode.chinese,
                                                engineArgs: engineArgs,
                                                scriptEncoding: scriptMode.scriptEncoding)
                    return AppleHost_Start(&cfg) == 1
                }
            }
        }
    }

    /// The engine thread waits here while the main thread shows the box.
    private static func askOnMainThread(text: String, caption: String, flags: UInt32) -> Int32 {
        let done = DispatchSemaphore(value: 0)
        var answer: Int32 = -1
        DispatchQueue.main.async {
            guard let present = presentMessageBox else {
                done.signal()
                return
            }
            present(text, caption, flags) { button in
                answer = button
                done.signal()
            }
        }
        done.wait()
        return answer
    }

    private static func withOptionalCString<R>(_ s: String?, _ body: (UnsafePointer<CChar>?) -> R) -> R {
        guard let s else { return body(nil) }
        return s.withCString { body($0) }
    }
}

/// The MessageBox buttons of the engine (os.h).
enum MessageBoxButtons {
    static let ok: Int32 = 1, cancel: Int32 = 2, retry: Int32 = 4, yes: Int32 = 6, no: Int32 = 7

    /// The buttons of a MessageBox flags value, first the default one's position.
    static func buttons(for flags: UInt32) -> [(title: String, id: Int32)] {
        switch flags & 0xf {
        case 1: return [("确定", ok), ("取消", cancel)]
        case 4: return [("是", yes), ("否", no)]
        case 5: return [("重试", retry), ("取消", cancel)]
        default: return [("确定", ok)]
        }
    }
}

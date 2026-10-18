import Foundation

/// The text encoding of the game's compiled scripts: the Chinese patch stores
/// GBK text in the same `BurikoCompiledScriptVer1.00` containers as the
/// original's Shift-JIS.
enum ScriptEncoding: String {
    case gbk
    case shiftJIS
    case unknown

    var language: GameLanguage? {
        switch self {
        case .gbk: return .chinese
        case .shiftJIS: return .japanese
        case .unknown: return nil
        }
    }

    var title: String {
        switch self {
        case .gbk: return "简体中文（GBK 汉化脚本）"
        case .shiftJIS: return "日本語（Shift-JIS 原版脚本）"
        case .unknown: return "未能识别（请手动选择语言）"
        }
    }
}

/// Reads a sample of the compiled scripts and decides whether they are GBK
/// (the pre-applied Chinese patch) or Shift-JIS (the original release).
///
/// The scripts are Buriko-compiled text with the usual `「」、。` punctuation
/// in the dialogue.  GBK encodes those as `A1 B8`, `A1 B9`, `A1 A2`, `A1 A3`;
/// Shift-JIS as `81 75`, `81 76`, `81 41`, `81 42`, and its kana add more
/// pointers.  Counting those two-byte sequences over a few megabytes of the
/// script archive gives an unambiguous answer even though the archive also
/// holds binary tables (random bytes hit a given pair about once per 64 KiB).
enum ScriptInspector {
    static let scriptArchiveName = "data01000.arc"
    static let marker = Data("BurikoCompiledScriptVer1.00".utf8)
    /// Bytes inspected after the first marker (or from the start when the
    /// marker is missing).
    static let sampleLimit = 2 << 20

    /// The encoding of the scripts of `folder` (looks for `data01000.arc` in it).
    static func detect(in folder: URL) -> ScriptEncoding {
        guard let archive = GamePaths.file(named: scriptArchiveName, in: folder) else { return .unknown }
        return detect(scriptArchive: archive)
    }

    static func detect(scriptArchive url: URL) -> ScriptEncoding {
        guard let data = try? Data(contentsOf: url, options: [.mappedIfSafe]), !data.isEmpty else {
            return .unknown
        }
        let start: Int
        if let markerRange = data.range(of: marker) {
            start = markerRange.upperBound
        } else {
            start = 0
        }
        let end = min(data.count, start + sampleLimit)
        guard end > start else { return .unknown }
        let sample = data.subdata(in: start..<end)
        return classify(sample)
    }

    /// Classify a byte sample by its punctuation pairs (exposed for tests).
    static func classify(_ sample: Data) -> ScriptEncoding {
        var gbk = 0
        var shiftJIS = 0
        sample.withUnsafeBytes { raw in
            let bytes = raw.bindMemory(to: UInt8.self)
            guard bytes.count >= 2 else { return }
            var i = 0
            while i + 1 < bytes.count {
                let pair = UInt16(bytes[i]) << 8 | UInt16(bytes[i + 1])
                switch pair {
                case 0xA1B8, 0xA1B9, 0xA1A2, 0xA1A3: // 「 」 、 。 in GBK
                    gbk += 1
                    i += 2
                case 0x8175, 0x8176, 0x8141, 0x8142, 0x82A0, 0x82A2, 0x82A4: // 「 」 、 。 あ い う in Shift-JIS
                    shiftJIS += 1
                    i += 2
                default:
                    i += 1
                }
            }
        }
        // Random binary noise gives about one hit per 64 KiB per pair; a real
        // dialogue sample gives thousands.  Require a clear, size-scaled lead.
        let minimum = max(32, (sample.count / 65536) * 12)
        if gbk >= minimum && gbk > shiftJIS * 4 { return .gbk }
        if shiftJIS >= minimum && shiftJIS > gbk * 4 { return .shiftJIS }
        return .unknown
    }
}

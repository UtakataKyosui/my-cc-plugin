// 指定したアプリの一番手前のウィンドウの CGWindowID を標準出力に出す。
// screencapture -l <id> に渡すと、そのウィンドウだけを撮れる。画面全体や
// 矩形指定と違い、手前に重なった他アプリのウィンドウが写り込まない。
//
//   swift window-id.swift "Zenn Desktop"
//   screencapture -x -l"$(swift window-id.swift 'Zenn Desktop')" out.png
import CoreGraphics
import Foundation

let arguments = CommandLine.arguments
guard arguments.count > 1 else {
    FileHandle.standardError.write("usage: window-id.swift <owner name>\n".data(using: .utf8)!)
    exit(2)
}
let owner = arguments[1]

// onScreenOnly を付けないと、閉じたウィンドウや別デスクトップのものまで拾う。
let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
guard let windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] else {
    FileHandle.standardError.write("failed to list windows\n".data(using: .utf8)!)
    exit(1)
}

// 一覧は手前から順に並ぶ。最初に見つかったものが最前面のウィンドウになる。
for window in windows {
    guard let name = window[kCGWindowOwnerName as String] as? String, name == owner else {
        continue
    }
    // レイヤー 0 が通常のウィンドウ。影やツールチップは別レイヤーに来る。
    guard let layer = window[kCGWindowLayer as String] as? Int, layer == 0 else {
        continue
    }
    guard let id = window[kCGWindowNumber as String] as? Int else {
        continue
    }
    print(id)
    exit(0)
}

FileHandle.standardError.write("no window found for \(owner)\n".data(using: .utf8)!)
exit(1)

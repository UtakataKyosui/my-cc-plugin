#!/usr/bin/env python3
"""
PreToolUse hook: TDD 準拠チェック（Blocking）

Edit/Write ツール使用前に実行され、実装コードに対応するテストが
存在するかをチェックする。テストがない場合はブロックする。

追加チェック:
- 空（placeholder のみ）のテスト関数を検出してブロック
- cyclomatic complexity ベースの最低テスト数との比較（警告）
- 外部依存なし（stdlib のみ）
"""

import json
import os
import re
import sys

# ============================================================
# 設定ロード（settings.json からオーバーライド可能）
# ============================================================


def _load_tdd_settings() -> dict:
    """CLAUDE_PLUGIN_ROOT/settings.json から設定を読み込む"""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if plugin_root:
        settings_path = os.path.join(plugin_root, "settings.json")
        if os.path.isfile(settings_path):
            try:
                with open(settings_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
    return {}


_SETTINGS = _load_tdd_settings()


# ============================================================
# opt-in ゲート（DEFAULT DISABLED）
# ============================================================

_ENABLED_ENV_VALUES = {"1", "true", "yes", "on"}


def _is_tdd_enforce_enabled() -> bool:
    """TDD enforce フックを動作させるか判定する（デフォルト無効）

    明示的に有効化された場合のみ True を返す:
    - 環境変数 TDD_ENFORCE_ENABLED が {"1","true","yes","on"}（大文字小文字無視）
    - settings.json の tddEnforce.enabled が True

    オールインワンプラグインのデフォルトで全 Edit/Write をブロックしないよう
    opt-in 方式とする。
    """
    env = os.environ.get("TDD_ENFORCE_ENABLED")
    if env is not None and env.strip().lower() in _ENABLED_ENV_VALUES:
        return True
    tdd = _SETTINGS.get("tddEnforce", {})
    return isinstance(tdd, dict) and tdd.get("enabled") is True


def _coerce_int_setting(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_str_list_setting(value, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return default
    return [str(v) for v in value if isinstance(v, str)]


_MAIN_MAX_NON_MAIN_FUNCTIONS: int = _coerce_int_setting(
    _SETTINGS.get("mainFileThreshold", {}).get("maxNonMainFunctions"), 1
)
_MAIN_MAX_LINES: int = _coerce_int_setting(
    _SETTINGS.get("mainFileThreshold", {}).get("maxLines"), 20
)
_ADDITIONAL_EXCLUDE: list[str] = _coerce_str_list_setting(
    _SETTINGS.get("additionalExcludePatterns"), []
)
_COMPILED_EXCLUDES: list[re.Pattern] = []
for _pat in _ADDITIONAL_EXCLUDE:
    try:
        _COMPILED_EXCLUDES.append(re.compile(_pat))
    except re.error:
        print(
            f"[tdd-enforce] ⚠️ additionalExcludePatterns の正規表現が無効です: {_pat!r}",
            file=sys.stderr,
        )


def _count_non_main_functions(file_path: str) -> int:
    """main 以外の関数定義数を数える（main.* ファイルの除外判定に使用）"""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return 0

    if ext == ".rs":
        fns = re.findall(r"\bfn\s+(\w+)\s*[(<]", content)
        return sum(1 for name in fns if name != "main")
    elif ext == ".py":
        fns = re.findall(r"^\s*def\s+(\w+)", content, re.MULTILINE)
        return sum(1 for name in fns if name != "main")
    elif ext == ".go":
        fns = re.findall(r"^\s*func\s+(?:\([^)]+\)\s*)?(\w+)", content, re.MULTILINE)
        return sum(1 for name in fns if name != "main")
    return 0


def _count_loc(file_path: str) -> int:
    """コメント・空行を除いたコード行数（LOC）を返す"""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return 0

    c_style = ext in (
        ".rs",
        ".go",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".java",
        ".cs",
        ".kt",
        ".kts",
        ".swift",
    )
    count = 0
    in_block_comment = False
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if c_style:
            if in_block_comment:
                if "*/" in s:
                    in_block_comment = False
                continue
            if "/*" in s:
                in_block_comment = True
                # 同一行で閉じている場合はコード行としてカウントしない
                if "*/" in s[s.index("/*") + 2 :]:
                    in_block_comment = False
                continue
            if s.startswith("//"):
                continue
        elif ext in (".py", ".rb", ".ex", ".exs") and s.startswith("#"):
            continue
        count += 1
    return count


def _should_exclude_main_file(file_path: str) -> bool:
    """main.* ファイルをテスト対象から除外するか判定する

    - 新規ファイル（未存在）→ 除外（テストブロックしない）
    - LOC > _MAIN_MAX_LINES → テスト対象（ビジネスロジックあり）
    - 非 main 関数数 > _MAIN_MAX_NON_MAIN_FUNCTIONS → テスト対象
    - それ以外 → 除外（純粋なエントリーポイント）
    """
    if not os.path.isfile(file_path):
        return True  # 新規作成時はスキップ

    loc = _count_loc(file_path)
    if loc > _MAIN_MAX_LINES:
        return False  # 大きいファイルはテスト対象

    non_main = _count_non_main_functions(file_path)
    return non_main <= _MAIN_MAX_NON_MAIN_FUNCTIONS


def read_input():
    """stdin から PreToolUse の JSON データを読み取る"""
    try:
        data = json.loads(sys.stdin.read())
        return data
    except (json.JSONDecodeError, EOFError, OSError, UnicodeDecodeError):
        return None


def extract_file_path(data):
    """ツール実行データからファイルパスを抽出する"""
    if not data:
        return None
    tool_input = data.get("tool_input", {})
    if "file_path" in tool_input:
        return tool_input["file_path"]
    return None


def is_excluded_file(file_path):
    """テスト不要なファイルかどうか判定する"""
    basename = os.path.basename(file_path)

    # ~/.claude/ 配下はグローバル Claude 設定（workflow/skill/hook）であり、
    # プロジェクトのソースコードではないため除外する
    abs_path = os.path.abspath(os.path.expanduser(file_path))
    claude_dir = os.path.expanduser("~/.claude/")
    if abs_path.startswith(claude_dir) or "/.claude/" in file_path.replace("\\", "/"):
        return True

    # settings.json の additionalExcludePatterns によるカスタム除外（正規表現で判定）
    for compiled in _COMPILED_EXCLUDES:
        if compiled.match(basename):
            return True

    # 設定ファイル
    config_patterns = [
        r".*\.config\.",
        r".*\.json$",
        r".*\.yaml$",
        r".*\.yml$",
        r".*\.toml$",
        r".*\.lock$",
        r".*\.env.*",
        r"Cargo\.toml$",
        r"Cargo\.lock$",
        r"package\.json$",
        r"package-lock\.json$",
        r"tsconfig.*\.json$",
        r"go\.mod$",
        r"go\.sum$",
        r"Makefile$",
        r"Dockerfile.*",
        r"docker-compose.*",
        r"\.gitignore$",
        r"\.eslintrc.*",
        r"\.prettierrc.*",
    ]

    for pattern in config_patterns:
        if re.match(pattern, basename):
            return True

    # ドキュメント
    if basename.lower().endswith((".md", ".txt", ".rst")):
        return True
    if basename.upper() in ("LICENSE", "LICENCE", "CHANGELOG", "AUTHORS"):
        return True

    # 型定義のみ
    if basename.endswith((".d.ts", ".types.ts")):
        return True

    # バレルファイル
    if basename in ("index.ts", "index.tsx", "index.js", "index.jsx"):
        return True

    # __init__.py
    if basename == "__init__.py":
        return True

    # CI/CD
    if "/.github/" in file_path or "/.circleci/" in file_path:
        return True

    # main エントリーポイント: LOC・非 main 関数数で判定（設定可能）
    if basename in ("main.rs", "main.go", "main.py"):
        return _should_exclude_main_file(file_path)

    # mod.rs (Rust モジュール宣言)
    if basename == "mod.rs":
        return True

    # C# バレル的な役割・プロジェクト設定
    if basename in ("AssemblyInfo.cs",) or basename.endswith(".csproj"):
        return True

    # Ruby プロジェクト設定
    if basename in ("Gemfile", "Rakefile") or basename.endswith(".gemspec"):
        return True

    # Elixir プロジェクト設定
    if basename == "mix.exs":
        return True

    # Swift プロジェクト設定
    if basename == "Package.swift":
        return True

    # Kotlin/Java ビルド設定
    gradle_files = (
        "build.gradle",
        "settings.gradle",
        "build.gradle.kts",
        "settings.gradle.kts",
    )
    if basename in gradle_files:
        return True

    # CSS / HTML / 画像等
    non_code_ext = (
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".html",
        ".htm",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
    )
    return any(basename.endswith(ext) for ext in non_code_ext)


def is_test_file(file_path):
    """テストファイルかどうか判定する"""
    basename = os.path.basename(file_path)

    # TypeScript / JavaScript
    if re.match(r".*\.(test|spec)\.(ts|tsx|js|jsx)$", basename):
        return True

    # Python
    if re.match(r"^test_.*\.py$", basename) or re.match(r".*_test\.py$", basename):
        return True
    if basename == "conftest.py":
        return True

    # Go
    if basename.endswith("_test.go"):
        return True

    # Java
    if re.match(r".*Test\.java$", basename) or re.match(r".*Tests\.java$", basename):
        return True

    # C#
    if re.match(r".*Tests?\.cs$", basename):
        return True

    # Ruby
    if (
        re.match(r".*_spec\.rb$", basename)
        or re.match(r"^test_.*\.rb$", basename)
        or re.match(r".*_test\.rb$", basename)
    ):
        return True

    # Elixir
    if re.match(r".*_test\.exs$", basename):
        return True

    # Swift
    if re.match(r".*Tests?\.swift$", basename):
        return True

    # Kotlin
    if re.match(r".*Tests?\.kt$", basename):
        return True

    # テストディレクトリ内
    path_parts = file_path.replace("\\", "/").split("/")
    test_dirs = {"__tests__", "tests", "spec", "test", "Tests"}
    return bool(test_dirs & set(path_parts))


def is_source_code(file_path):
    """ソースコードファイルかどうか判定する"""
    code_extensions = (
        ".rs",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".vue",
        ".svelte",
        ".py",
        ".go",
        ".java",
        ".cs",
        ".rb",
        ".ex",
        ".exs",
        ".swift",
        ".kt",
        ".kts",
    )
    return any(file_path.endswith(ext) for ext in code_extensions)


def find_project_root(file_path):
    """プロジェクトルートを探す"""
    current = os.path.dirname(file_path)
    markers = [
        "Cargo.toml",
        "package.json",
        "go.mod",
        "pyproject.toml",
        ".git",
        "Gemfile",  # Ruby
        "mix.exs",  # Elixir
        "Package.swift",  # Swift
        "build.gradle",  # Kotlin/Java
        "build.gradle.kts",  # Kotlin
    ]
    for _ in range(10):  # 最大10階層
        for marker in markers:
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def _check_rust_inline_test(file_path) -> str | None:
    """Rust テストを探す。インライン→file_path、統合→テストパス、なし→None"""
    name_without_ext = os.path.splitext(os.path.basename(file_path))[0]
    project_root = find_project_root(file_path)

    if not os.path.isfile(file_path):
        # 新規ファイル作成時: 統合テストがあれば OK
        if project_root:
            tests_dir = os.path.join(project_root, "tests")
            integration = os.path.join(tests_dir, f"{name_without_ext}.rs")
            if os.path.isfile(integration):
                return integration
        return None

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        if "#[cfg(test)]" in content or "#[test]" in content:
            return file_path  # インラインテストあり
        if project_root:
            tests_dir = os.path.join(project_root, "tests")
            if os.path.isdir(tests_dir):
                for fname in os.listdir(tests_dir):
                    fname_stem = os.path.splitext(fname)[0]
                    if fname.endswith(".rs") and fname_stem == name_without_ext:
                        return os.path.join(tests_dir, fname)
        return None
    except OSError:
        return file_path  # 読めない場合はパス


def find_test_file(file_path) -> str | None:
    """対応するテストファイルのパスを返す（見つからなければ None）"""
    dirname = os.path.dirname(file_path)
    basename = os.path.basename(file_path)
    name_without_ext = os.path.splitext(basename)[0]
    ext = os.path.splitext(basename)[1]

    # Rust: 同一ファイル内の #[cfg(test)] または外部統合テスト
    if ext == ".rs":
        return _check_rust_inline_test(file_path)

    # TypeScript / JavaScript
    if ext in (".ts", ".tsx", ".js", ".jsx"):
        test_patterns = [
            os.path.join(dirname, f"{name_without_ext}.test{ext}"),
            os.path.join(dirname, f"{name_without_ext}.spec{ext}"),
            os.path.join(dirname, "__tests__", f"{name_without_ext}{ext}"),
            os.path.join(dirname, "__tests__", f"{name_without_ext}.test{ext}"),
        ]
        if ext == ".tsx":
            test_patterns.append(os.path.join(dirname, f"{name_without_ext}.test.ts"))
        elif ext == ".ts":
            test_patterns.append(os.path.join(dirname, f"{name_without_ext}.test.tsx"))
        for p in test_patterns:
            if os.path.exists(p):
                return p
        return None

    # Vue / Svelte — test files use TypeScript convention
    if ext in (".vue", ".svelte"):
        test_patterns = [
            os.path.join(dirname, f"{name_without_ext}.test.ts"),
            os.path.join(dirname, f"{name_without_ext}.spec.ts"),
            os.path.join(dirname, f"{name_without_ext}.test.tsx"),
            os.path.join(dirname, f"{name_without_ext}.spec.tsx"),
            os.path.join(dirname, "__tests__", f"{name_without_ext}.test.ts"),
            os.path.join(dirname, "__tests__", f"{name_without_ext}.spec.ts"),
        ]
        for p in test_patterns:
            if os.path.exists(p):
                return p
        return None

    # Python
    if ext == ".py":
        test_patterns = [
            os.path.join(dirname, f"test_{basename}"),
            os.path.join(dirname, f"{name_without_ext}_test.py"),
            os.path.join(dirname, "tests", f"test_{basename}"),
            os.path.join(os.path.dirname(dirname), "tests", f"test_{basename}"),
        ]
        for p in test_patterns:
            if os.path.exists(p):
                return p
        return None

    # Go
    if ext == ".go":
        test_patterns = [
            os.path.join(dirname, f"{name_without_ext}_test.go"),
            os.path.join(dirname, f"{name_without_ext}_integration_test.go"),
        ]
        for p in test_patterns:
            if os.path.exists(p):
                return p
        return None

    # Java
    if ext == ".java":
        test_patterns = [
            os.path.join(dirname, f"{name_without_ext}Test.java"),
            os.path.join(dirname, f"{name_without_ext}Tests.java"),
        ]
        if "/src/main/" in file_path:
            test_dir = file_path.replace("/src/main/", "/src/test/")
            test_dir = os.path.dirname(test_dir)
            test_patterns.extend(
                [
                    os.path.join(test_dir, f"{name_without_ext}Test.java"),
                    os.path.join(test_dir, f"{name_without_ext}Tests.java"),
                ]
            )
        for p in test_patterns:
            if os.path.exists(p):
                return p
        return None

    # C#
    if ext == ".cs":
        test_patterns = [
            os.path.join(dirname, f"{name_without_ext}Tests.cs"),
            os.path.join(dirname, f"{name_without_ext}Test.cs"),
        ]
        project_root = find_project_root(file_path)
        if project_root:
            try:
                for entry in os.scandir(project_root):
                    if entry.is_dir() and ("Test" in entry.name):
                        rel = os.path.relpath(dirname, project_root)
                        test_patterns.append(
                            os.path.join(entry.path, rel, f"{name_without_ext}Tests.cs")
                        )
                        test_patterns.append(
                            os.path.join(entry.path, rel, f"{name_without_ext}Test.cs")
                        )
            except OSError:
                pass
        for p in test_patterns:
            if os.path.exists(p):
                return p
        return None

    # Ruby
    if ext == ".rb":
        project_root = find_project_root(file_path)
        test_patterns = [
            os.path.join(dirname, f"{name_without_ext}_spec.rb"),
            os.path.join(dirname, f"test_{basename}"),
            os.path.join(dirname, f"{name_without_ext}_test.rb"),
        ]
        if project_root:
            rel = os.path.relpath(file_path, project_root).replace("\\", "/")
            if rel.startswith("lib/"):
                spec_path = rel.replace("lib/", "spec/", 1).replace(".rb", "_spec.rb")
                test_patterns.append(os.path.join(project_root, spec_path))
                test_path = rel.replace("lib/", "test/", 1).replace(".rb", "_test.rb")
                test_patterns.append(os.path.join(project_root, test_path))
        for p in test_patterns:
            if os.path.exists(p):
                return p
        return None

    # Elixir
    if ext in (".ex", ".exs"):
        project_root = find_project_root(file_path)
        test_patterns = [
            os.path.join(dirname, f"{name_without_ext}_test.exs"),
        ]
        if project_root:
            rel = os.path.relpath(file_path, project_root).replace("\\", "/")
            if rel.startswith("lib/"):
                test_path = rel.replace("lib/", "test/", 1)
                test_path_base, _ = os.path.splitext(test_path)
                test_path = test_path_base + "_test.exs"
                test_patterns.append(os.path.join(project_root, test_path))
        for p in test_patterns:
            if os.path.exists(p):
                return p
        return None

    # Swift
    if ext == ".swift":
        project_root = find_project_root(file_path)
        test_patterns = [
            os.path.join(dirname, f"{name_without_ext}Tests.swift"),
            os.path.join(dirname, f"{name_without_ext}Test.swift"),
        ]
        if project_root:
            try:
                rel = os.path.relpath(dirname, project_root)
                for entry in os.scandir(project_root):
                    is_test_dir = "Tests" in entry.name or "Test" in entry.name
                    if entry.is_dir() and is_test_dir:
                        test_dir_path = os.path.join(entry.path, rel)
                        test_patterns.append(
                            os.path.join(
                                test_dir_path, f"{name_without_ext}Tests.swift"
                            )
                        )
                        test_patterns.append(
                            os.path.join(test_dir_path, f"{name_without_ext}Test.swift")
                        )
            except OSError:
                pass
        for p in test_patterns:
            if os.path.exists(p):
                return p
        return None

    # Kotlin
    if ext in (".kt", ".kts"):
        test_patterns = [
            os.path.join(dirname, f"{name_without_ext}Test.kt"),
            os.path.join(dirname, f"{name_without_ext}Tests.kt"),
        ]
        file_path_fwd = file_path.replace("\\", "/")
        for src_marker in ("/src/main/kotlin/", "/src/main/java/"):
            if src_marker in file_path_fwd:
                test_dir_path = file_path_fwd.replace(src_marker, "/src/test/kotlin/")
                test_dir = os.path.dirname(test_dir_path)
                test_patterns.extend(
                    [
                        os.path.join(test_dir, f"{name_without_ext}Test.kt"),
                        os.path.join(test_dir, f"{name_without_ext}Tests.kt"),
                    ]
                )
        for p in test_patterns:
            if os.path.exists(p):
                return p
        return None

    return file_path  # 未対応言語はパス（ブロックしない）


# ============================================================
# cyclomatic complexity 近似（分岐キーワード数）
# ============================================================

_BRANCH_KEYWORDS: dict = {
    # else if は if を含むため \bif\b で二重カウントしないよう除外
    ".rs": [r"\bif\b", r"\bwhile\b", r"\bfor\b", r"\bloop\b", r"\bmatch\b", r"\?"],
    ".ts": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b"],
    ".tsx": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b"],
    ".js": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b"],
    ".jsx": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b"],
    ".vue": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b"],
    ".svelte": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b"],
    ".py": [
        r"\bif\b",
        r"\belif\b",
        r"\bfor\b",
        r"\bwhile\b",
        r"\bexcept\b",
        r"\band\b",
        r"\bor\b",
    ],
    ".go": [r"\bif\b", r"\bfor\b", r"\bcase\b", r"\bselect\b"],
    ".java": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bcase\b"],
    ".cs": [
        r"\bif\b",
        r"\bfor\b",
        r"\bforeach\b",
        r"\bwhile\b",
        r"\bcase\b",
    ],
    ".rb": [
        r"\bif\b",
        r"\belsif\b",
        r"\bunless\b",
        r"\bwhile\b",
        r"\bfor\b",
        r"\brescue\b",
    ],
    ".ex": [r"\bif\b", r"^\s*->", r"\bcase\b", r"\bcond\b"],
    ".exs": [r"\bif\b", r"^\s*->", r"\bcase\b", r"\bcond\b"],
    ".swift": [
        r"\bif\b",
        r"\bguard\b",
        r"\bfor\b",
        r"\bwhile\b",
        r"\bcase\b",
    ],
    ".kt": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bwhen\b"],
    ".kts": [r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bwhen\b"],
}


def _find_comment_marker(line: str, marker: str) -> int:
    """文字列リテラルを考慮してコメントマーカーの開始位置を返す。-1 は未検出。

    print("//") のような行でコメントマーカーが文字列内にある場合は -1 を返す。
    """
    in_str = False
    str_char = ""
    i = 0
    n = len(line)
    mlen = len(marker)
    while i < n:
        c = line[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                i += 2  # エスケープシーケンスをスキップ
                continue
            if c == str_char:
                in_str = False
        else:
            if c in ('"', "'"):
                in_str = True
                str_char = c
            elif line[i : i + mlen] == marker:
                return i
        i += 1
    return -1


def _strip_comment_lines(lines: list[str], ext: str) -> list[str]:
    """コメント行を除去する（文字列リテラル内のコメントマーカーを誤認しない版）"""
    result = []
    in_block = False
    c_style = ext in (
        ".rs",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".vue",
        ".svelte",
        ".go",
        ".java",
        ".cs",
        ".kt",
        ".kts",
        ".swift",
    )
    for line in lines:
        stripped = line.strip()
        if c_style:
            if in_block:
                if "*/" in line:
                    in_block = False
                continue
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            block_idx = _find_comment_marker(line, "/*")
            if block_idx != -1:
                if "*/" not in line[block_idx + 2 :]:
                    in_block = True
                line = line[:block_idx]
            inline_idx = _find_comment_marker(line, "//")
            if inline_idx != -1:
                line = line[:inline_idx]
        elif ext in (".py", ".rb", ".ex", ".exs"):
            if stripped.startswith("#"):
                continue
            inline_idx = _find_comment_marker(line, "#")
            if inline_idx != -1:
                line = line[:inline_idx]
        result.append(line)
    return result


def count_branch_keywords(file_path: str) -> int:
    """ソースファイルの分岐キーワード数（cyclomatic complexity の近似）を返す"""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            raw_lines = [ln.rstrip() for ln in f.readlines()]
    except OSError:
        return 0

    code_lines = _strip_comment_lines(raw_lines, ext)
    patterns = _BRANCH_KEYWORDS.get(ext, [])

    # C 系言語のみ &&/|| を論理演算子として追加カウント
    c_style_logical = ext in (
        ".rs",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".java",
        ".cs",
        ".kt",
        ".kts",
        ".swift",
    )

    count = 0
    for line in code_lines:
        # ブランチキーワードを出現回数分カウント
        for p in patterns:
            count += len(re.findall(p, line))
        # C 系言語: &&/|| を分岐として追加カウント
        if c_style_logical:
            count += len(re.findall(r"&&|\|\|", line))
    return count


# ============================================================
# テスト関数数カウント
# ============================================================


def count_test_functions(test_file: str, source_ext: str) -> int:
    """テストファイル内のテスト関数数を返す"""
    if not os.path.isfile(test_file):
        return 0
    try:
        with open(test_file, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return 0

    if source_ext == ".rs":
        return len(re.findall(r"#\[test\]", content))
    elif source_ext in (".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"):
        return len(re.findall(r"\b(?:it|test)\s*\(", content))
    elif source_ext == ".py":
        return len(re.findall(r"^\s*def test_", content, re.MULTILINE))
    elif source_ext == ".go":
        return len(re.findall(r"^func Test\w+\(", content, re.MULTILINE))
    elif source_ext == ".java" or source_ext in (".kt", ".kts"):
        return len(re.findall(r"@Test\b", content))
    elif source_ext == ".cs":
        return len(re.findall(r"\[(?:Test|TestMethod|Fact|Theory)\]", content))
    elif source_ext == ".rb":
        return len(re.findall(r"^\s*(?:it|specify)\s+['\"]", content, re.MULTILINE))
    elif source_ext in (".ex", ".exs"):
        return len(re.findall(r'^\s*test\s+[\'"]', content, re.MULTILINE))
    elif source_ext == ".swift":
        return len(re.findall(r"func test\w+\(", content))
    return 0


# ============================================================
# 空テスト検出
# ============================================================

_PLACEHOLDER_RE = re.compile(
    r"^\s*(?:"
    r"pass"
    r"|todo!\s*\(\s*\)"
    r"|unimplemented!\s*\(\s*\)"
    r"|//\s*(?:TODO|FIXME|todo|fixme)"
    r"|#\s*(?:TODO|FIXME|todo|fixme)"
    r"|raise\s+NotImplementedError"
    r"|pending(?:\s|$)"
    r"|skip(?:\s|$)"
    r")\s*[;]?\s*$"
)


def _is_placeholder_line(line: str) -> bool:
    return bool(_PLACEHOLDER_RE.match(line))


def _collect_block_body(lines: list[str], start: int, max_lines: int = 30) -> list[str]:
    """行インデックス start の { から対応する } までの本体行を収集する"""
    body = []
    depth = 0
    for i in range(start, min(start + max_lines, len(lines))):
        body.append(lines[i])
        depth += lines[i].count("{") - lines[i].count("}")
        if depth <= 0 and i > start:
            break
    return body[1:]  # 宣言行を除く


def find_empty_test_names(test_file: str, source_ext: str) -> list[str]:
    """空（placeholder のみ）のテスト関数名リストを返す"""
    if not os.path.isfile(test_file):
        return []
    try:
        with open(test_file, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return []

    empty: list[str] = []

    def _is_empty_body(body_lines: list[str]) -> bool:
        content = [
            ln for ln in body_lines if ln.strip() and ln.strip() not in ("{", "}")
        ]
        return not content or all(_is_placeholder_line(ln) for ln in content)

    if source_ext == ".rs":
        for i, line in enumerate(lines):
            if "#[test]" in line:
                # 次の fn 行を探す
                j = i + 1
                while j < len(lines) and "fn " not in lines[j]:
                    j += 1
                if j < len(lines):
                    m = re.search(r"fn\s+(\w+)", lines[j])
                    name = m.group(1) if m else f"test@{j + 1}"
                    body = _collect_block_body(lines, j)
                    if _is_empty_body(body):
                        empty.append(name)

    elif source_ext == ".py":
        for i, line in enumerate(lines):
            m = re.match(r"^\s*def (test_\w+)\s*\(", line)
            if m:
                name = m.group(1)
                base_indent = len(line) - len(line.lstrip())
                body: list[str] = []
                for j in range(i + 1, len(lines)):
                    ln = lines[j]
                    if (
                        ln.strip()
                        and (len(ln) - len(ln.lstrip())) <= base_indent
                        and j > i + 1
                    ):
                        break
                    body.append(ln)
                if _is_empty_body(body):
                    empty.append(name)

    elif source_ext in (".ts", ".tsx", ".js", ".jsx"):
        content = "".join(lines)
        for m in re.finditer(
            r"\b(?:it|test)\s*\(\s*(['\"`])((?:(?!\1).)*?)\1", content
        ):
            name = m.group(2)
            pos = m.end()
            brace = content.find("{", pos)
            if brace == -1 or brace - pos > 150:
                continue
            depth = 0
            end = brace
            for idx in range(brace, min(brace + 600, len(content))):
                if content[idx] == "{":
                    depth += 1
                elif content[idx] == "}":
                    depth -= 1
                    if depth == 0:
                        end = idx
                        break
            body_text = content[brace + 1 : end]
            body_lines = [ln for ln in body_text.splitlines() if ln.strip()]
            if _is_empty_body(body_lines):
                empty.append(name)

    elif source_ext == ".go":
        for i, line in enumerate(lines):
            m = re.match(r"^func (Test\w+)\(", line)
            if m:
                name = m.group(1)
                body = _collect_block_body(lines, i)
                if _is_empty_body(body):
                    empty.append(name)

    return empty


# ============================================================
# メイン
# ============================================================


def main():
    # opt-in ゲート: 明示的に有効化されていなければ何もしない（デフォルト無効）
    if not _is_tdd_enforce_enabled():
        sys.exit(0)

    data = read_input()
    file_path = extract_file_path(data)

    if not file_path:
        sys.exit(0)

    # ソースコードでなければスキップ
    if not is_source_code(file_path):
        sys.exit(0)

    # 除外ファイルはスキップ
    if is_excluded_file(file_path):
        sys.exit(0)

    # テストファイル自体の編集はスキップ
    if is_test_file(file_path):
        sys.exit(0)

    # テストファイルを探す
    test_file = find_test_file(file_path)
    basename = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()

    if test_file is None:
        print(
            f"[TDD] ⛔ テストが見つかりません: {basename}\n"
            f"[TDD] TDD では実装の前にテストを書く必要があります。\n"
            f"[TDD] まず対応するテストファイルを作成してください。\n"
            "[TDD] 💡 このチェックは opt-in です(環境変数 TDD_ENFORCE_ENABLED=1 "
            "または settings.json の tddEnforce.enabled で有効化)。"
            "個別除外は settings.json の additionalExcludePatterns(basename 一致)"
            "または ~/.claude/ 配下への配置で可能です。",
            file=sys.stderr,
        )
        sys.exit(2)

    # 空テスト検出（ブロック）
    empty_tests = find_empty_test_names(test_file, ext)
    if empty_tests:
        names = ", ".join(empty_tests[:5])
        suffix = f" 他{len(empty_tests) - 5}件" if len(empty_tests) > 5 else ""
        print(
            f"[TDD] ⛔ 空のテスト関数が検出されました: {names}{suffix}\n"
            "[TDD] placeholder(pass / todo!() 等)のみのテストは\n"
            "[TDD] Red フェーズとして無効です。\n"
            f"[TDD] テストに具体的なアサーションを追加してください。\n"
            "[TDD] 💡 このチェックは opt-in です(環境変数 TDD_ENFORCE_ENABLED=1 "
            "または settings.json の tddEnforce.enabled で有効化)。"
            "個別除外は settings.json の additionalExcludePatterns(basename 一致)"
            "または ~/.claude/ 配下への配置で可能です。",
            file=sys.stderr,
        )
        sys.exit(2)

    # 最低テスト数チェック（警告のみ、新規ファイルはスキップ）
    if os.path.isfile(file_path):
        cc = count_branch_keywords(file_path)
        min_tests = cc + 1
        actual = count_test_functions(test_file, ext)
        if actual < min_tests:
            print(
                f"[TDD] ⚠️  テスト数が推奨を下回っています: {basename}\n"
                f"[TDD] 分岐キーワード数: {cc} → 推奨最低テスト数: {min_tests} 件\n"
                f"[TDD] 現在のテスト数: {actual} 件\n"
                f"[TDD] 正常系・異常系・境界値のテストケースを追加してください。",
                file=sys.stderr,
            )
            # 警告のみ、ブロックしない

    sys.exit(0)


if __name__ == "__main__":
    main()

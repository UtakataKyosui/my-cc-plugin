---
name: tdd-enforce
description: テスト駆動開発（TDD）の方法論とRed-Green-Refactorサイクルの実践ガイド。テストの書き方、言語別テストフレームワークの選定、TDDパターンを提供する。テスト、TDD、テスト駆動、ユニットテスト、テストファーストに関する質問時に使用する。
globs:
  - "**/*.test.*"
  - "**/*.spec.*"
  - "**/*_test.*"
  - "**/test_*.*"
  - "**/tests/**"
  - "**/__tests__/**"
---

# Test-Driven Development (TDD) Enforcement Guide

## TDD の基本原則

**すべての実装コードには、対応するテストが必要。テストを先に書き、テストが失敗することを確認してから実装する。**

### Red-Green-Refactor サイクル

1. **Red**: 失敗するテストを書く
   - 実装したい振る舞いをテストとして記述
   - テストを実行し、失敗することを確認（コンパイルエラーも Red）
2. **Green**: テストをパスする最小限のコードを書く
   - テストを通すために必要最小限のコードだけを実装
   - 完璧な設計は後回し
3. **Refactor**: コードを改善する
   - テストがパスした状態を維持しながらリファクタリング
   - 重複排除、命名改善、構造整理

### テスト設計パターン

**Arrange-Act-Assert (AAA)**:
```
// Arrange: テストの準備
// Act: テスト対象の実行
// Assert: 結果の検証
```

**Given-When-Then**:
```
// Given: 前提条件
// When: 操作
// Then: 期待結果
```

## 言語別テストフレームワーク Quick Reference

| 言語 | フレームワーク | コマンド |
|---|---|---|
| Rust | cargo test (built-in) | `cargo test` |
| TypeScript/JS | Vitest | `npx vitest` |
| TypeScript/JS | Jest | `npx jest` |
| Python | pytest | `pytest` |
| Go | testing (built-in) | `go test ./...` |
| C# | xUnit / NUnit | `dotnet test` |
| Java | JUnit 5 | `mvn test` / `gradle test` |
| Ruby | RSpec / Minitest | `rspec` / `ruby -Itest` |
| Elixir | ExUnit (built-in) | `mix test` |
| Swift | XCTest (built-in) | `swift test` |

## テストファイル命名規則

| 言語 | テストファイルパターン | 例 |
|---|---|---|
| Rust | 同一ファイル内 `#[cfg(test)]` or `tests/` | `src/lib.rs`, `tests/integration.rs` |
| TypeScript | `{name}.test.ts`, `{name}.spec.ts` | `Button.test.tsx` |
| Python | `test_{name}.py`, `{name}_test.py` | `test_parser.py` |
| Go | `{name}_test.go` | `parser_test.go` |
| Java | `{Name}Test.java` | `ParserTest.java` |

## opt-in フラグ（DEFAULT DISABLED）

TDD enforce フック（`hooks/scripts/check-test-exists.py`）は **デフォルトで無効** です。
明示的に有効化したときのみ Edit/Write をブロックします。

有効化する方法（どちらか一方で OK）:

- 環境変数: `TDD_ENFORCE_ENABLED=1`（`true` / `yes` / `on` も可、大文字小文字無視）
- 設定ファイル: `settings.json` の `tddEnforce.enabled` を `true` にする

```json
{
  "tddEnforce": { "enabled": true }
}
```

**なぜ opt-in か**: このプラグインはオールインワン構成のため、デフォルトで TDD ブロックを
有効にすると全ての Edit/Write 操作がテスト不在を理由にブロックされ、TDD を採用していない
利用者の妨げになる。そのため明示的に有効化したプロジェクトでのみ動作する。

## TDD でテストが不要なもの（実装と一致する完全な除外リスト）

`is_excluded_file()` は以下を除外する（テストブロックの対象外）:

- **設定ファイル**: `*.config.*`, `*.json`, `*.yaml`, `*.yml`, `*.toml`, `*.lock`,
  `.env*`, `Cargo.toml`, `Cargo.lock`, `package.json`, `package-lock.json`,
  `tsconfig*.json`, `go.mod`, `go.sum`, `Makefile`, `Dockerfile*`, `docker-compose*`,
  `.gitignore`, `.eslintrc*`, `.prettierrc*`
- **ドキュメント**: `*.md`, `*.txt`, `*.rst`, `LICENSE` / `LICENCE` / `CHANGELOG` / `AUTHORS`
- **型定義のみ**: `*.d.ts`, `*.types.ts`
- **バレルファイル**: `index.ts` / `index.tsx` / `index.js` / `index.jsx`
- **`__init__.py`**（Python パッケージ宣言）
- **CI/CD**: パスに `/.github/` または `/.circleci/` を含むファイル
- **main エントリーポイント**: `main.rs` / `main.go` / `main.py`
  （LOC と 非 main 関数数のしきい値で判定 — 下記 `mainFileThreshold` 参照）
- **`mod.rs`**（Rust モジュール宣言）
- **C# プロジェクト設定**: `AssemblyInfo.cs`, `*.csproj`
- **Ruby プロジェクト設定**: `Gemfile`, `Rakefile`, `*.gemspec`
- **Elixir プロジェクト設定**: `mix.exs`
- **Swift プロジェクト設定**: `Package.swift`
- **Kotlin/Java ビルド設定**: `build.gradle`, `settings.gradle`,
  `build.gradle.kts`, `settings.gradle.kts`
- **CSS / HTML / 画像等**: `.css`, `.scss`, `.sass`, `.less`, `.html`, `.htm`,
  `.svg`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.ico`, `.woff`, `.woff2`, `.ttf`, `.eot`
- **グローバル Claude 設定ディレクトリ**: 絶対パスが `~/.claude/` 配下、または
  パスに `/.claude/` セグメントを含むファイル（workflow / skill / hook は
  プロジェクトソースではないため除外）

## settings.json の調整項目（knobs）

`CLAUDE_PLUGIN_ROOT/settings.json` で以下を上書きできる:

- **`tddEnforce.enabled`**（boolean, デフォルト `false`）: フック全体の有効化フラグ（上記参照）
- **`additionalExcludePatterns`**（文字列の配列, 正規表現）: 追加の除外パターン。
  **注意: マッチ対象は basename のみ**（フルパスではない）。例: `["^generated_.*\\.py$"]`
- **`mainFileThreshold`**: `main.*` ファイルをテスト対象とするか判定するしきい値
  - `maxNonMainFunctions`（int, デフォルト `1`）: main 以外の関数がこの数を超えるとテスト対象
  - `maxLines`（int, デフォルト `20`）: LOC がこの数を超えるとテスト対象

個別ファイルを除外したい場合は `additionalExcludePatterns`（basename 一致）に追加するか、
スクリプトを `~/.claude/` 配下に配置する。

## 詳細ドキュメント

- [test-case-design.md](./test-case-design.md) - テストケース設計（正常系/異常系/境界値の列挙手順）
- [testing-frameworks.md](./testing-frameworks.md) - 言語別テストフレームワーク詳細ガイド（パラメータ化テスト統一ガイド含む）
- [tdd-patterns.md](./tdd-patterns.md) - TDD パターン・プロパティベース・ミューテーション・スナップショット・キャラクタリゼーションテスト
- [test-design.md](./test-design.md) - テスト設計の原則とベストプラクティス
- [ide-ci-integration.md](./ide-ci-integration.md) - IDE/CI/pre-commit/jj-vcs-workflow 連携ガイド

## 計算式スキル

テスト最低数の計算式と正常系/異常系の分類ルールは `tdd-enforce:formula` スキル（「テスト数の計算式を説明して」で起動）を参照。

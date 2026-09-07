# IDE / CI 連携ガイド

TDD を日常開発に組み込むための IDE・CI パイプライン・pre-commit フックとの連携方法。

---

## IDE 連携

### VS Code

**推奨拡張機能**:

| 拡張機能 | 説明 |
|----------|------|
| [Vitest](https://marketplace.visualstudio.com/items?itemName=vitest.explorer) | Vitest テストエクスプローラー、インラインテスト結果 |
| [Jest](https://marketplace.visualstudio.com/items?itemName=Orta.vscode-jest) | Jest テストエクスプローラー、watch モード |
| [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer) | Rust テスト実行・デバッグ |
| [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python) | pytest 統合 |
| [Coverage Gutters](https://marketplace.visualstudio.com/items?itemName=ryanluker.vscode-coverage-gutters) | カバレッジをエディタのガターに表示 |

**settings.json（TDD 推奨設定）**:
```json
{
  "vitest.enable": true,
  "vitest.watchMode": true,
  "jest.autoRun": "watch",
  "rust-analyzer.checkOnSave.command": "test",
  "editor.formatOnSave": true
}
```

### JetBrains IDE（IntelliJ / WebStorm / CLion / PyCharm）

- **Run/Debug Configuration** でテストランナーを設定し `Run in watch mode` をオン
- **Coverage** ツールウィンドウで行カバレッジを確認
- **Go to Test** (`Ctrl+Shift+T`) で実装 ↔ テストを素早く切り替え

---

## Watch モード（ファイル変更時に自動実行）

### Rust — cargo-watch

```bash
cargo install cargo-watch
cargo watch -x test              # ファイル変更時に cargo test を実行
cargo watch -x "test -- --nocapture"  # 標準出力も表示
```

### TypeScript — Vitest

```bash
npx vitest                       # watch モードで起動（デフォルト）
npx vitest --run                 # 1 回だけ実行
npx vitest --reporter=verbose    # 詳細出力
```

### TypeScript — Jest

```bash
npx jest --watch                 # 変更ファイルのみ
npx jest --watchAll              # 全テスト
```

### Python — pytest-watch

```bash
pip install pytest-watch
ptw                              # watch モード
ptw -- -v                        # オプション付き
```

### Go

```bash
# air（ホットリロードツール）を利用
go install github.com/air-verse/air@latest
# .air.toml で test コマンドを設定
```

---

## Pre-commit フック連携

### lefthook（推奨）

C2Lab で採用しているフックマネージャー。

```yaml
# lefthook.yml（使用する言語に応じてコマンドを選択・削除する）
pre-commit:
  commands:
    test-rust:
      # set -o pipefail を使い、パイプ途中の失敗を正しく伝播させる
      run: bash -c 'set -o pipefail; cargo test 2>&1 | tail -20'
    test-ts:
      run: npx vitest run
    test-py:
      run: pytest -x -q
    format-rust:
      run: cargo fmt --check
    format-ts:
      run: npx prettier --check .
```

### Husky（Node.js プロジェクト）

```bash
npm install -D husky
npx husky init
```

```bash
# .husky/pre-commit
# set -o pipefail を使い、パイプ途中の失敗を正しく伝播させる
bash -c 'set -o pipefail; npx vitest run --reporter=verbose 2>&1 | tail -20'
```

### Pre-commit フックでの TDD 保護

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: run-tests
        name: Run tests
        entry: npx vitest run
        language: node
        pass_filenames: false
        always_run: true
```

---

## CI パイプライン連携

### GitHub Actions — 基本構成

```yaml
# .github/workflows/test.yml（使用言語に応じたセットアップステップを追加する）
name: Tests

on: [push, pull_request]

jobs:
  test-rust:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - name: Run tests
        run: cargo test --all
      - name: Check coverage
        run: |
          cargo install cargo-tarpaulin
          cargo tarpaulin --out Xml

  test-ts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npx vitest run --coverage

  test-py:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: pytest -v
```

### GitHub Actions — Rust 詳細設定

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable

      - name: Run tests
        run: cargo test --all --verbose

      - name: Run mutation tests (PR only)
        if: github.event_name == 'pull_request'
        run: |
          cargo install cargo-mutants
          # set -o pipefail を使い、パイプ途中の失敗を正しく伝播させる
          bash -c 'set -o pipefail; cargo mutants --timeout 60 2>&1 | tail -30'
```

### GitHub Actions — TypeScript 詳細設定

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20

      - run: npm ci
      - run: npx vitest run --coverage --reporter=verbose

      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

---

## jj-vcs-workflow との連携

C2Lab の `jj-vcs-workflow` プラグインを使っている場合、TDD と Change 管理を組み合わせる:

```
Change 単位と TDD サイクルの対応:
  jj change #1: test-case-design.md に従ってテストケースを設計
  jj change #2: Red フェーズ（失敗するテストを書く）
  jj change #3: Green フェーズ（最小限の実装）
  jj change #4: Refactor フェーズ（コード改善）
```

**推奨ワークフロー**:

```bash
# 1. テストケース設計（Phase 0）
jj describe -m "test: add test cases for validate_email (Phase 0)"

# 2. Red フェーズ
jj new -m "test(Red): add failing tests for validate_email"
# テストを書く → cargo test で失敗を確認

# 3. Green フェーズ
jj new -m "feat(Green): implement validate_email"
# 実装を書く → cargo test でパスを確認

# 4. Refactor
jj new -m "refactor: extract validation logic"
# リファクタリング → テストが通り続けることを確認
```

### TDD サイクルと PR の粒度

| パターン | 説明 | 推奨場面 |
|----------|------|---------|
| 1 機能 1 PR | Red/Green/Refactor すべてを 1 PR に含める | 小〜中規模の機能 |
| フェーズ別 PR | Red + Green を 1 PR、Refactor を別 PR | レビューを細かくしたい場合 |
| テスト先行 PR | テストのみ先にマージ、実装を後のPRで | 設計合意が重要な場合 |

---

## カバレッジ計測ツール

| 言語 | ツール | コマンド |
|------|--------|---------|
| Rust | cargo-tarpaulin | `cargo tarpaulin --out Html` |
| TypeScript | v8 / istanbul | `npx vitest run --coverage` |
| Python | pytest-cov | `pytest --cov=src --cov-report=html` |
| Go | built-in | `go test -coverprofile=coverage.out ./...` |
| Kotlin/Java | JaCoCo | `./gradlew jacocoTestReport` |
| C# | dotnet-coverage | `dotnet test --collect:"Code Coverage"` |

**カバレッジの目安**:
- ライン/ブランチカバレッジ 80% 以上を目標
- ただし数値より「重要なパスがカバーされているか」が本質
- カバレッジ 100% を目指すよりも、リスクの高い箇所を重点的にカバーする

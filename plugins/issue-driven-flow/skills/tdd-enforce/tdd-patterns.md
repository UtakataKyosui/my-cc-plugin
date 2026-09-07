# TDD パターンとアンチパターン

## TDD の基本パターン

### 1. Obvious Implementation（明白な実装）

テストが明白な場合、直接正しい実装を書く。

```
Red:   test_add(2, 3) → expected 5
Green: fn add(a, b) { a + b }  // 明白なので直接実装
```

### 2. Fake It（偽装実装）

まずハードコードで通し、徐々に一般化する。

```
Red:   test_add(2, 3) → expected 5
Green: fn add(a, b) { 5 }      // まずハードコード
Red:   test_add(1, 1) → expected 2
Green: fn add(a, b) { a + b }  // 一般化
```

### 3. Triangulation（三角測量）

複数のテストケースで実装を強制する。

```
test_add(2, 3) → 5
test_add(0, 0) → 0
test_add(-1, 1) → 0
// 3つのテストで add の正しい実装が決まる
```

### 4. One to Many（1つから多数へ）

単一要素のテストから始め、コレクションへ拡張する。

```
Red:   test_sum([5]) → 5
Green: fn sum(list) { list[0] }
Red:   test_sum([1, 2, 3]) → 6
Green: fn sum(list) { list.iter().sum() }
```

## テスト作成の原則

### FIRST 原則

- **F**ast: テストは高速に実行される
- **I**ndependent: テスト間に依存関係がない
- **R**epeatable: 何度実行しても同じ結果
- **S**elf-validating: テスト自体が合否を判定する
- **T**imely: 実装の前にテストを書く（TDD）

### テストの命名規則

**何をテストしているかが名前から分かること。**

```
// Good
test_parse_valid_json_returns_object()
test_parse_invalid_json_returns_error()
test_empty_input_returns_none()

// Bad
test1()
test_parse()
test_it_works()
```

**パターン**: `test_{対象}_{条件}_{期待結果}`

### テストのサイズ

- **1テスト = 1アサーション**（原則）
- 複数アサーションは関連する場合のみ許可
- テスト関数は10-15行以内を目安
- Arrange が大きい場合はフィクスチャやヘルパーに抽出

## TDD サイクルの実践

### ステップ 1: Red（失敗するテストを書く）

```rust
#[test]
fn test_parse_number() {
    let result = parse("42");
    assert_eq!(result, Token::Number(42));
}
```

この時点で `parse` 関数も `Token` 型も存在しない → コンパイルエラー = Red。

### ステップ 2: Green（最小限の実装）

```rust
enum Token {
    Number(i32),
}

fn parse(input: &str) -> Token {
    Token::Number(input.parse().unwrap())
}
```

テストがパスする最小限のコード。エラーハンドリングは後回し。

### ステップ 3: Refactor

```rust
fn parse(input: &str) -> Result<Token, ParseError> {
    let n = input.parse::<i32>().map_err(|_| ParseError::InvalidNumber)?;
    Ok(Token::Number(n))
}
```

テストを更新しながらリファクタリング。

### ステップ 4: 次のテスト

```rust
#[test]
fn test_parse_invalid_input() {
    let result = parse("abc");
    assert!(result.is_err());
}
```

新しいテストケースで次の Red を作る。

## アンチパターン

### 1. Test After（後付けテスト）

```
// BAD: 実装してからテストを書く
fn complex_function() { ... }  // 先に実装
#[test] fn test_complex() { ... }  // 後からテスト

// GOOD: テストを先に書く
#[test] fn test_complex() { ... }  // 先にテスト（Red）
fn complex_function() { ... }      // テストを通す実装（Green）
```

**問題**: テスト可能な設計にならない。テストが実装に引きずられる。

### 2. Testing Implementation（実装の詳細テスト）

```
// BAD: 内部実装をテスト
assert_eq!(cache.internal_map.len(), 3);

// GOOD: 振る舞いをテスト
assert_eq!(cache.get("key"), Some("value"));
```

### 3. Fragile Tests（壊れやすいテスト）

```
// BAD: 出力の全文一致
assert_eq!(output, "Error at line 5: unexpected token ';'");

// GOOD: 重要な部分のみ検証
assert!(output.contains("unexpected token"));
assert!(output.contains("line 5"));
```

### 4. God Test（巨大テスト）

```
// BAD: 1テストで複数の振る舞いを検証
#[test]
fn test_everything() {
    // 20行のセットアップ
    // パース、変換、保存、通知を全部テスト
}

// GOOD: 1テスト1振る舞い
#[test] fn test_parse() { ... }
#[test] fn test_transform() { ... }
#[test] fn test_save() { ... }
```

### 5. Slow Tests（遅いテスト）

```
// BAD: テスト内でネットワーク通信
fn test_fetch_data() {
    let data = http_client.get("https://api.example.com");
}

// GOOD: モックを使用
fn test_fetch_data() {
    let mock_client = MockHttpClient::new();
    mock_client.expect_get().returning(|_| Ok(sample_data()));
}
```

## テストピラミッド

```
        /  E2E  \        少量（遅い、高コスト）
       /----------\
      / Integration \    中程度
     /----------------\
    /   Unit Tests     \  大量（速い、低コスト）
   /--------------------\
```

- **Unit Tests**: 70-80%。個々の関数・メソッド。高速。
- **Integration Tests**: 15-20%。モジュール間連携。
- **E2E Tests**: 5-10%。ユーザーシナリオ。最も遅い。

## TDD で書くべきでないテスト

- 外部ライブラリの機能テスト（信頼する）
- 単純な getter/setter
- フレームワークが生成したボイラープレート
- 設定ファイルのバリデーション（CI/lint に任せる）

---

## プロパティベーステスト（Property-Based Testing）

手動でテストケースを列挙する代わりに、**数学的性質（プロパティ）** を定義してランダム入力で検証する。
正常系/異常系の境界を人間が見落とすケースを発見するのに有効。

**いつ使うか**:
- 純粋関数（副作用なし）で入力空間が広い場合
- エンコード/デコード、シリアライズ/デシリアライズの可逆性確認
- ソート・フィルタなどのアルゴリズム正確性確認

### Rust — proptest

```toml
[dev-dependencies]
proptest = "1"
```

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_add_commutative(a: i32, b: i32) {
        // プロパティ: 加算は可換
        prop_assert_eq!(add(a, b), add(b, a));
    }

    #[test]
    fn test_encode_decode_roundtrip(s in ".*") {
        let encoded = encode(&s);
        prop_assert_eq!(decode(&encoded), s);
    }
}
```

### TypeScript / JavaScript — fast-check

```bash
npm install -D fast-check
```

```typescript
import fc from 'fast-check';

test('add is commutative', () => {
  fc.assert(
    fc.property(fc.integer(), fc.integer(), (a, b) => {
      expect(add(a, b)).toBe(add(b, a));
    })
  );
});

test('encode/decode roundtrip', () => {
  fc.assert(
    fc.property(fc.string(), (s) => {
      expect(decode(encode(s))).toBe(s);
    })
  );
});
```

### Python — Hypothesis

```bash
pip install hypothesis
```

```python
from hypothesis import given, strategies as st

@given(st.integers(), st.integers())
def test_add_commutative(a, b):
    assert add(a, b) == add(b, a)

@given(st.text())
def test_encode_decode_roundtrip(s):
    assert decode(encode(s)) == s
```

### Go — Fuzz Testing（Go 1.18+）

```go
func FuzzAdd(f *testing.F) {
    f.Add(2, 3)  // seed corpus
    f.Fuzz(func(t *testing.T, a, b int) {
        result := Add(a, b)
        if result != Add(b, a) {
            t.Errorf("Add not commutative: Add(%d, %d) != Add(%d, %d)", a, b, b, a)
        }
    })
}
```

```bash
go test -fuzz=FuzzAdd -fuzztime=10s
```

### Elixir — StreamData

```elixir
# mix.exs
{:stream_data, "~> 0.6", only: :test}
```

```elixir
defmodule CalculatorTest do
  use ExUnit.Case
  use ExUnitProperties

  property "add is commutative" do
    check all a <- integer(), b <- integer() do
      assert Calculator.add(a, b) == Calculator.add(b, a)
    end
  end
end
```

---

## ミューテーションテスト（Mutation Testing）

ソースコードに意図的なバグ（ミューテーション）を注入し、テストがそれを検出できるかを測定する。
テストの**質**（アサーションの強さ）を評価する手法。

**概念**:
```
元のコード: if x > 0 { ... }
ミューテント: if x >= 0 { ... }  // >= に変更
→ 既存テストがこのミューテントを殺せるか？
```

**ミューテーションスコア** = 殺せたミューテント数 / 総ミューテント数 × 100%

**いつ使うか**:
- コードカバレッジが高いのにバグが出る場合
- テストの強度を定量的に評価したい場合

### Rust — cargo-mutants

```bash
cargo install cargo-mutants
cargo mutants
```

```
MISSED: src/lib.rs:5:17: replace > with >= in if x > 0
→ テストを追加して境界値 x=0 をカバーする
```

### TypeScript / JavaScript — Stryker

```bash
npm install -D @stryker-mutator/core @stryker-mutator/vitest-runner
```

```json
// stryker.config.json
{
  "testRunner": "vitest",
  "coverageAnalysis": "perTest"
}
```

```bash
npx stryker run
```

### Python — mutmut

```bash
pip install mutmut
mutmut run
mutmut results
```

### ミューテーションテスト結果の読み方

| 結果 | 意味 | 対応 |
|------|------|------|
| Killed ✅ | テストがバグを検出した | 良好 |
| Survived ❌ | テストがバグを見落とした | テスト強化が必要 |
| Timeout | テストが無限ループに | 要調査 |

---

## スナップショットテスト（Snapshot Testing）

関数・コンポーネントの出力を**スナップショット（基準値）** として保存し、以降の変更で差分を検出する。
UI コンポーネントやシリアライズ出力のリグレッション防止に有効。

**注意**: スナップショットテストは回帰テストであり、TDD の Red フェーズには使わない。
Refactor フェーズで既存の振る舞いを凍結する用途（Characterization Test）に向く。

### Rust — insta

```toml
[dev-dependencies]
insta = "1"
```

```rust
use insta::assert_snapshot;

#[test]
fn test_format_output() {
    let result = format_report(&data);
    assert_snapshot!(result);
    // 初回実行で snap ファイル生成、以降は差分チェック
}
```

```bash
cargo insta review  # スナップショットの承認/拒否
cargo insta test    # スナップショットテスト実行
```

### TypeScript — Vitest snapshot

```typescript
import { expect, it } from 'vitest';

it('formats report correctly', () => {
  const result = formatReport(data);
  expect(result).toMatchSnapshot();
});

// インラインスナップショット
it('formats short output inline', () => {
  expect(format('hello')).toMatchInlineSnapshot(`"Hello!"`)
});
```

```bash
npx vitest -u  # スナップショット更新（--update）
```

### TypeScript — Jest snapshot

```typescript
test('renders component', () => {
  const { container } = render(<MyComponent />);
  expect(container).toMatchSnapshot();
});
```

```bash
npx jest --updateSnapshot
```

### スナップショットのベストプラクティス

- スナップショットファイルは **Git にコミットする**（レビュー対象）
- 意図的な変更のみ `npx vitest -u`（Vitest）または `npx jest --updateSnapshot`（Jest）で更新する
- スナップショットが大きすぎる場合は、出力の一部のみアサートするテストに切り替える
- UI コンポーネントのスナップショットは `@testing-library/react` のセマンティックアサーションと組み合わせる

---

## キャラクタリゼーションテスト（Characterization Test）

**既存のコードの「実際の振る舞い」を凍結する**テスト。テストのない既存コードをリファクタリングする前に書く。

> "Characterization tests describe the actual, current behavior of a piece of software, and protect existing behavior of legacy code against unintended changes when refactoring."
> — Michael Feathers, *Working Effectively with Legacy Code*

### いつ使うか

- テストのないレガシーコードをリファクタリングする前
- 外部 API レスポンスや複雑なビジネスロジックの出力を凍結したい場合
- バグを修正する際、バグ修正後も他の振る舞いが変わっていないことを保証したい場合

### TDD との違い

| | TDD | キャラクタリゼーション |
|---|---|---|
| タイミング | 実装**前**に書く | 実装**後**に書く |
| 目的 | 設計を導く | 既存の振る舞いを凍結する |
| 期待値 | 正しい値を人間が決める | 実際の出力をそのまま使う |
| 使う場面 | 新機能開発 | リファクタリング前、レガシーコード |

### 手順

```
1. テストを書く（何を期待するかまだ分からない）
2. テストを実行する → 実際の出力を観察する
3. 観察した出力を期待値としてアサーションに書く
4. テストを再実行して Green を確認
5. リファクタリングを開始
6. テストが通り続けることを確認しながら変更する
```

### Rust — insta でキャラクタリゼーション

```rust
use insta::assert_snapshot;

#[test]
fn characterize_legacy_formatter() {
    // 期待値を最初は空にして実行し、スナップショットを自動生成する
    let result = legacy_format(&complex_input());
    assert_snapshot!(result);
    // `cargo insta review` で実際の出力を承認 → 以後は差分をガード
}
```

### TypeScript — Vitest でキャラクタリゼーション

```typescript
import { expect, it } from 'vitest';

it('characterizes legacy transform output', () => {
  const result = legacyTransform(complexInput);
  // 初回: toMatchSnapshot() でスナップショット生成
  expect(result).toMatchSnapshot();
});
```

### Python — pytest でキャラクタリゼーション

```python
import json
from pathlib import Path

def test_characterize_legacy_processor(snapshot):
    result = legacy_processor(complex_input())
    # syrupy 等の snapshot ライブラリを使用
    assert result == snapshot

# syrupy を使わない場合: 出力をファイルに書き出して比較
# UPDATE=1 pytest で初回ゴールデンファイルを作成。通常実行では missing が失敗扱い。
def test_characterize_output():
    import os
    result = legacy_processor(complex_input())
    expected_file = Path("tests/fixtures/expected_output.json")
    if os.environ.get("UPDATE") == "1":
        expected_file.parent.mkdir(parents=True, exist_ok=True)
        expected_file.write_text(json.dumps(result, indent=2))
    assert expected_file.exists(), f"Golden file missing. Run: UPDATE=1 pytest {__file__}"
    assert result == json.loads(expected_file.read_text())
```

### Go — ゴールデンファイルパターン

```go
import (
    "flag"
    "os"
    "testing"
)

var update = flag.Bool("update", false, "update golden files")

func TestCharacterizeLegacyOutput(t *testing.T) {
    result := legacyProcessor(complexInput())
    golden := "testdata/expected_output.golden"

    if *update {
        if err := os.WriteFile(golden, []byte(result), 0644); err != nil {
            t.Fatalf("failed to write golden file: %v", err)
        }
    }

    expected, err := os.ReadFile(golden)
    if err != nil {
        t.Fatalf("golden file missing. Run: go test -update")
    }
    if result != string(expected) {
        t.Errorf("output differs from golden file")
    }
}
```

```bash
go test -update  # ゴールデンファイルを更新
go test          # 差分チェック
```

### Refactor フェーズでの使い方

```
TDD サイクルの Refactor フェーズ:
1. Green（テストパス済み）の状態から Refactor に入る前に
2. キャラクタリゼーションテストで追加の出力をスナップショットとして凍結
3. リファクタリング中にスナップショットテストが通り続けることを確認
4. リファクタリング完了後、意図的な変更のみスナップショットを更新する
```

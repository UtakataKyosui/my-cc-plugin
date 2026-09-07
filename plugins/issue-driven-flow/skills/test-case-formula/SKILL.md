---
name: tdd-enforce:formula
description: This skill should be used when the user asks "テストの最低数はどう計算するの？", "なぜこの計算式なの？", "組み合わせテストの根拠を教えて", "how is the minimum test count calculated?", "explain the test coverage formula", "what is the Cartesian product for testing?", "テストケースの内訳を説明して", "正常系と異常系の分け方を教えて". Explains the mathematical basis for calculating the minimum number of tests based on feature counts and their Cartesian product. Applies to any function, method, or UI component.
version: 1.1.0
---

# テスト最低数の計算式

## 基本原理

対象（関数・メソッド・UIコンポーネント）の因子を**正常系バリアント**と**異常系因子**に分類し、それぞれの直積から最低テスト数を算出する。

```
正常系テスト数    = Π(正常系バリアント因子の値数)
異常系パターン数  = Π(異常系因子の値数)
最低テスト数合計  = 正常系テスト数 × 異常系パターン数
```

> Π は「直積（Cartesian product）」。

---

## 正常系 / 異常系の分類ルール

### 汎用関数・メソッド

| 因子の種類 | 分類 | 理由 |
|---|---|---|
| 必須 enum/union 引数（`'asc' \| 'desc'`, `'json' \| 'csv'` 等） | **正常系バリアント** | 全値が「有効な設定」であり、バリエーションテストの軸 |
| `boolean` 型引数/フラグ | **異常系** | `true` が無効・エラー状態を表すことが多い |
| optional 引数（`?` / `\| undefined` / `\| null`） | **異常系** | 省略ケース自体がエッジケース |
| エラー系引数・フラグ（`throwOnError`, `strict` 等） | **異常系** | エラー分岐を制御する |
| callback / higher-order function 引数 | **異常系** | コールバックの失敗・エラーを含むエッジケース |

### UIコンポーネント（追加ルール）

| 因子の種類 | 分類 | 理由 |
|---|---|---|
| 必須 enum/union props（`variant`, `size`, `type` 等） | **正常系バリアント** | コンポーネントの「設定の組み合わせ」を表す |
| `boolean` 型 props/states | **異常系** | `true` が無効・ロード・エラー状態を表すことが多い |
| optional props（`?` / `\| undefined`） | **異常系** | 省略ケース自体がエッジケース |
| event handlers（`() => void` 等） | **異常系** | コールバックの失敗・エラーを含むエッジケース |
| React states（`useState` 等） | **異常系** | ランタイムで変化する一時的な状態 |
| Union に `'error'` `'loading'` `'disabled'` を含む | **異常系** | エラー状態を示すリテラルが含まれる |

---

## 計算例: 汎用関数

```
function formatDate(
  date: Date,
  format: 'iso' | 'locale' | 'unix',   → 3通り  【正常系バリアント: required enum】
  timezone?: string,                    → 2通り  【異常系: optional】
  throwOnInvalid?: boolean              → 2通り  【異常系: boolean flag】
): string
```

**計算:**
```
正常系: format(3) = 3
異常系パターン: timezone(2) × throwOnInvalid(2) = 4
合計: 3 × 4 = 12
  ├─ 純正常系テスト: 3
  └─ 異常系を含むテスト: 9
```

**内訳:**
- **3 純正常系テスト**: `timezone=省略, throwOnInvalid=省略` で iso/locale/unix 各フォーマット
- **3 timezone 指定テスト**: 各フォーマット × timezone 指定あり
- **3 throwOnInvalid テスト**: 各フォーマット × throwOnInvalid=true で無効日付を渡す
- **残り 3**: timezone + throwOnInvalid の複合パターン × 各フォーマット

---

## 計算例: UIコンポーネント

```
Props:
  variant: 'primary' | 'secondary' | 'danger'  → 3通り  【正常系バリアント: required enum】
  size: 'sm' | 'md' | 'lg'                      → 3通り  【正常系バリアント: required enum】
  disabled?: boolean                             → 2通り  【異常系: optional boolean】
  onClick: () => void                            → 2通り  【異常系: event handler】

States:
  isLoading: boolean                             → 2通り  【異常系: state】
```

**計算:**
```
正常系: variant(3) × size(3) = 9
異常系パターン: disabled(2) × onClick(2) × isLoading(2) = 8
合計: 9 × 8 = 72
  ├─ 純正常系テスト: 9
  └─ 異常系を含むテスト: 63
```

---

## 言語別の型 → 値数変換表

### TypeScript / JavaScript

| 型表現 | 値数 | 分類 |
|---|---|---|
| `boolean` | 2 | 異常系 |
| `'a' \| 'b' \| 'c'` | 3 | 正常系（全リテラルが有効値） |
| `string` | 2 | 正常系（有効値 / 空文字） |
| `number` | 2 | 正常系（正常値 / 境界値） |
| `T \| undefined` | count(T) + 1 | 異常系（optional） |
| `T \| null` | count(T) + 1 | 異常系（nullable） |
| `T[]` | 2 | 正常系（空配列 / 非空配列） |
| `() => void` | 2 | 異常系（event handler） |
| 文字列リテラル `'x'` | 1 | — |

### Rust

| 型表現 | 値数 | 分類 |
|---|---|---|
| `bool` | 2 | 異常系 |
| `Option<T>` | count(T) + 1 | 異常系（None ケース） |
| `Result<T, E>` | count(T) + count(E) | 異常系（Err ケース） |
| enum（variants N 個） | N | 正常系（全 variant が有効） or 異常系（エラー variant 含む） |
| `Vec<T>` | 2 | 正常系（空 / 非空） |
| `&str` / `String` | 2 | 正常系（有効 / 空文字） |
| `i32` / `u32` 等 | 2 | 正常系（正常値 / 境界値・0・最大値） |

### Python

| 型表現 | 値数 | 分類 |
|---|---|---|
| `bool` | 2 | 異常系 |
| `Optional[T]` / `T \| None` | count(T) + 1 | 異常系 |
| `Literal['a', 'b', 'c']` | 3 | 正常系 |
| `str` | 2 | 正常系（有効 / 空文字） |
| `int` / `float` | 2 | 正常系（正常値 / 境界値） |
| `list[T]` | 2 | 正常系（空 / 非空） |
| `Callable[..., T]` | 2 | 異常系（コールバック） |

### Go

| 型表現 | 値数 | 分類 |
|---|---|---|
| `bool` | 2 | 異常系 |
| `*T`（ポインタ） | count(T) + 1 | 異常系（nil ケース） |
| `error`（戻り値） | 2 | 異常系（nil / non-nil） |
| `string` | 2 | 正常系（有効 / 空文字） |
| `int` 等 | 2 | 正常系（正常値 / 境界値） |
| `[]T` | 2 | 正常系（空 / 非空） |

---

## なぜ正常系と異常系を分けるのか

分けない場合、「全組み合わせ = すべて正常系のバリアントテスト」として実装してしまうことが多い。

実際には:
- **正常系テスト**: 各設定・バリアントが正しく動作するか
- **異常系テスト**: optional 省略・boolean フラグ ON・エラー入力・null/None 時の動作

の 2 種類が必要であり、用途が異なる。

---

## 現実的な解釈

**直積は理論的最小値**であり、実際のプロジェクトでは:

- **優先度付け**: 高リスク・高頻度の組み合わせを優先
- **ペアワイズテスト**: 2因子間の全組み合わせに限定（直積より少ない）
- **リスクベース**: 重要な機能パスに絞る

出力される数値は「理論的最小値」であり、実際のテスト追加目標の**下限参考値**として使う。
最低でも `normalTests` 件の純正常系テストと、主要な異常系パターンを網羅する必要がある。

---

## 参考リソース

- UIコンポーネント解析スクリプト: `${CLAUDE_PLUGIN_ROOT}/scripts/ui_test_coverage.py`
- UI カバレッジ分析の実行: `tdd-enforce:ui-coverage-analyze` スキル
- テストケース一覧の設計手順: 正常系・異常系の洗い出しと組み合わせ整理

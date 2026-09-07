---
name: tdd-enforce:test-case-design
description: This skill should be used when the user asks "テストケースを洗い出して", "何をテストすべきか整理して", "正常系・異常系を列挙して", "テスト設計をして", "test cases for this function", "enumerate test cases", "what should I test?", "TDD サイクルの前にテスト計画を立てたい". Given a function/method/feature description, enumerates normal, error, and boundary test cases in a structured table before writing any code.
version: 1.1.0
---

# テストケース設計ガイド

## 概要

TDD サイクルの Red フェーズに入る前に、実装対象の**テストケース一覧を先に設計**する。
正常系 N 件 / 異常系 M 件 / 境界値 K 件の最低テスト数と内訳を表形式で出力し、漏れを防ぐ。

---

## テストケース設計の手順

### Step 1: 対象の入力・出力・分岐を分析する

以下の観点で対象を分解する:

1. **引数/入力の型と制約**
   - 各引数の型（`string`, `number`, `Option<T>`, `Result<T>`, enum 等）
   - 必須 vs optional
   - 取りうる値のドメイン（有効範囲・許可値セット）

2. **出力/戻り値**
   - 正常時の戻り値型
   - エラー時の戻り値型（`Result::Err`, 例外, `null` 等）
   - 副作用（I/O, 状態変更）

3. **制御フロー（分岐）**
   - `if/else`, `match/switch`, ガード節の数
   - 早期 return のパス
   - ループ（0回・1回・N回）

### Step 2: 因子を正常系/異常系/境界値に分類する

| 因子の種類 | 分類 | 代表的なテスト値 |
|---|---|---|
| 必須 enum/union 引数（全値が有効） | **正常系バリアント** | 各 variant を個別テスト |
| `boolean` フラグ | **異常系 or 正常系** | エラーフラグ（`throwOnError`）は異常系、単なる挙動切替フラグ（`verbose`）は正常系バリアントとして扱う |
| optional 引数（`?` / `\| undefined` / `\| null` / `Option<T>` / `None`） | **正常系 or 異常系** | 省略時にデフォルト動作が期待される場合は正常系（準正常系）、省略が不正な入力の場合は異常系 |
| エラー系引数（`throwOnError`, `strict` 等） | **異常系** | `true` で不正入力を与える |
| callback / handler | **異常系** | 成功時・失敗/例外時 |
| 数値引数（`i32`, `f64`, `number` 等） | **境界値** | `0`, `-1`, `MAX`, `MIN`, 通常値 |
| 文字列引数 | **境界値** | 空文字 `""`, 最大長, Unicode, 特殊文字 |
| コレクション（`Vec<T>`, `T[]`, `list` 等） | **境界値** | 空コレクション, 要素1個, 大量要素 |
| null/None 可能な参照 | **境界値** | `null`/`None`, 有効参照 |

### Step 3: テストケース一覧テーブルを出力する

以下のフォーマットで出力する:

```
## テストケース一覧: {関数名/機能名}

### 概要
- 正常系テスト: N 件
- 異常系テスト: M 件
- 境界値テスト: K 件
- 合計: N+M+K 件

### 正常系テスト（N 件）
| # | テスト名 | Given（入力） | When（操作） | Then（期待結果） |
|---|----------|---------------|--------------|-----------------|
| 1 | 正常値での処理 | ... | ... | ... |

### 異常系テスト（M 件）
| # | テスト名 | Given（入力） | When（操作） | Then（期待結果） |
|---|----------|---------------|--------------|-----------------|
| 1 | null 入力でエラー | ... | ... | ... |

### 境界値テスト（K 件）
| # | テスト名 | Given（入力） | When（操作） | Then（期待結果） |
|---|----------|---------------|--------------|-----------------|
| 1 | 空文字列 | ... | ... | ... |
```

---

## 設計例: `formatDate(date, format, timezone?)` 関数

**シグネチャ**:
```typescript
function formatDate(
  date: Date,
  format: 'iso' | 'locale' | 'unix',
  timezone?: string
): string
```

**分析**:
- `date`: 必須 Date 型 → 有効 Date / 無効 Date（境界値）
- `format`: 必須 enum（3 variant）→ 正常系バリアント × 3
- `timezone?`: optional string → **正常系（準正常系：省略時は UTC デフォルト）** + 境界値（無効タイムゾーン）

**テストケース一覧: `formatDate`**

| 概要 | 件数 |
|---|---|
| 正常系 | 6件（iso / locale / unix 各フォーマット × timezone指定あり/省略） |
| 異常系 | 0件 |
| 境界値 | 4件（無効Date、エポック、未来日時、無効timezone） |
| 合計 | 10件 |

### 正常系テスト（6 件）

| # | テスト名 | Given | When | Then |
|---|----------|-------|------|------|
| 1 | ISO フォーマット（timezone省略） | `new Date('2024-01-15')`, `'iso'` | `formatDate(date, 'iso')` | UTC で `"2024-01-15T..."` 形式 |
| 2 | locale フォーマット（timezone省略） | `new Date('2024-01-15')`, `'locale'` | `formatDate(date, 'locale')` | UTC でロケール文字列 |
| 3 | unix フォーマット（timezone省略） | `new Date('2024-01-15')`, `'unix'` | `formatDate(date, 'unix')` | UNIX タイムスタンプ文字列 |
| 4 | ISO + タイムゾーン指定 | `date`, `'iso'`, `'Asia/Tokyo'` | `formatDate(date, 'iso', 'Asia/Tokyo')` | JST でフォーマット |
| 5 | locale + タイムゾーン指定 | `date`, `'locale'`, `'Asia/Tokyo'` | `formatDate(date, 'locale', 'Asia/Tokyo')` | JST でローカライズ |
| 6 | unix + タイムゾーン指定 | `date`, `'unix'`, `'Asia/Tokyo'` | `formatDate(date, 'unix', 'Asia/Tokyo')` | UNIX タイムスタンプ文字列 |

### 境界値テスト（4 件）

| # | テスト名 | Given | When | Then |
|---|----------|-------|------|------|
| 7 | 無効 Date | `new Date('invalid')`, `'iso'` | `formatDate(date, 'iso')` | エラーまたは `"Invalid Date"` |
| 8 | エポック（0） | `new Date(0)`, `'unix'` | `formatDate(date, 'unix')` | `"0"` |
| 9 | 未来日時 | `new Date('2099-12-31')`, `'iso'` | `formatDate(date, 'iso')` | 正常にフォーマット |
| 10 | 無効タイムゾーン | `date`, `'iso'`, `'Invalid/Zone'` | `formatDate(date, 'iso', 'Invalid/Zone')` | エラーまたはフォールバック |

---

## 設計例: Rust `parse_config(path: &Path) -> Result<Config, ConfigError>`

**分析**:
- `path`: ファイルパス → 存在する/しない/権限なし（境界値・異常系）
- 戻り値 `Result<Config, ConfigError>`: 成功 / 失敗ケースが明確

| 概要 | 件数 |
|---|---|
| 正常系 | 2件（最小設定、フル設定） |
| 異常系 | 4件（ファイル不在、権限なし、不正 TOML、必須キー欠如） |
| 境界値 | 2件（空ファイル、最大サイズ） |
| 合計 | 8件 |

---

## 最低テスト数の目安

分岐キーワード（`if`, `match`, `?`, `else`, `for`, `while`, `&&`, `||`）の数を数え、`分岐数 + 1` が最低テスト関数数の目安。

```
# Rust 関数の例
fn validate(s: &str, max_len: usize) -> Result<(), Error> {
    if s.is_empty() { return Err(...); }       // 分岐 +1
    if s.len() > max_len { return Err(...); }  // 分岐 +1
    if s.contains('\0') { return Err(...); }   // 分岐 +1
    Ok(())
}
# 分岐数 3 → 最低 4 テスト（3+1）
```

---

## テストケース一覧の使い方（cycle.md との連携）

1. このスキルでテストケース一覧テーブルを生成
2. ユーザーが承認・修正
3. `cycle.md` の Phase 1（Red）でテーブルの **1 行ずつ**を順に Red-Green でこなす
4. 全行が Green になったら Refactor フェーズへ

テーブルを先に作ることで「次に何をテストするか」が明確になり、TDD が単発ではなく**連続した反復**として機能する。

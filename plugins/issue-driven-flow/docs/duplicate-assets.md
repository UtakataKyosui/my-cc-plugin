# 重複アセットのカノニカル方針（dotclaude × issue-driven-flow プラグイン）

> Status: **提案（要ユーザー確認）** — Issue #11
>
> 本ドキュメントは「どちらを正本（canonical）とするか」を**決定・記録するだけ**のドキュメントである。
> スキルの削除・移動・編集は一切行わない。最終的な方針確定にはユーザーの確認を必要とする。

> ## ⚠️ 2026-06-25 更新（Issue #19 により一部 superseded）
>
> 本ドキュメントの **`jj-safe-new` / `jj-safe-push` に関する結論（Option C ＝ プラグイン側 Skill コピーを正本とする）は Issue #19 で覆された**。
> 両 Skill の**入口（`SKILL.md`）は廃止**し、参照は `jj safe-push` / `jj safe-new` の**エイリアスコマンド**へ一本化した。
> （履歴）Issue #21 では **jj-safe 安全網一式を外部ツール [jj-exec-aliases](https://github.com/UtakataKyosui/jj-exec-aliases) に集約**し、当時のプラグインから撤去した。撤去対象は jj 専用 hook 4 つ、実行系スクリプト、`settings.json` の `jj safe-*` permission だった。この判断はalias実体の所在に関するものであり、今回の統合でalias有無を検出する薄い誘導hookのみ再導入している。
> 現在このプラグインは **jj safe-* のalias実体を持たない**。aliasとシェルラッパーは jj-exec-aliases が提供する（各自 opt-in で導入）。今回の統合で、aliasが存在する場合だけ動作するブロックhookを issue-driven-flow に再統合した。`scripts/push.py` はalias未導入時に素の `jj git push`（確認後 push）へフォールバックする。
> 理由: `disable-model-invocation` の Skill 入口や jj 固有 hook は、配布プラグインに個人ツール依存を持ち込み、無駄なツール往復や保守の重複を生んでいた。安全網は jj-exec-aliases に一本化するのが正しい所在である。
> なお運用方針として **`my-task`（gh-my-task）を終了し `gh wheel` へ移行する**（Option C の my-task 判断は本更新で無効化）。ただし **リポジトリ内の `my-task` Skill 実体（`skills/my-task/`）や `gh my-task` を前提とするコマンド（例: `commands/issue-driven-flow/status.md`）の `gh wheel` 置き換えは本 PR のスコープ外**であり、別途対応する。以下 §2・§5・§7 の jj-safe-* / my-task に関する記述は当時の決定の記録として残す。

## 1. 背景

以下の 3 つのアセットが、ユーザーの個人 `~/.claude` 設定リポジトリ（**UtakataKyosui/dotclaude**）と、
配布用プラグイン（**issue-driven-flow**）の **両方に重複して存在** している。

Issue #11 は、これらについて「どちらを正本とするか」を決定し、方針を記録することを求めている。

## 2. 重複している 3 アセットと所在

| アセット | dotclaude（個人 `~/.claude`） | このプラグイン（issue-driven-flow） | 種別 |
|---|---|---|---|
| `jj-safe-new` | あり（個人グローバルスキル + alias / hook） | ~~`plugins/issue-driven-flow/skills/jj-safe-new/SKILL.md`~~ → **Issue #19 で削除**。~~実体は `scripts/jj-safe-new.sh` + hook + alias~~ → **Issue #21 で撤去し外部ツール jj-exec-aliases に集約（プラグインは非保持）** | 安全クリティカルな VCS（jj）操作（Skill 入口は廃止） |
| `jj-safe-push` | あり（個人グローバルスキル + PreToolUse hook + シェル関数ラッパー） | ~~`plugins/issue-driven-flow/skills/jj-safe-push/SKILL.md`~~ → **Issue #19 で削除**。~~実体は `scripts/jj-safe-push.sh` + hook + alias~~ → **Issue #21 で撤去し外部ツール jj-exec-aliases に集約（プラグインは非保持）** | 安全クリティカルな VCS（jj）操作（Skill 入口は廃止） |
| `gh-my-task`（プラグインでは `my-task`） | あり（`gh my-task` 拡張のラッパースキル） | `plugins/issue-driven-flow/skills/my-task/SKILL.md` | PR 管理ユーティリティ（`gh` 拡張依存） |

### 各スキルの要約と性質

- **`jj-safe-new`**: jj で Change 境界を安全に越える唯一の方法。スコープチェック（`.claude/jj-scope.json` の許可ファイル照合）と品質チェック（Lefthook pre-commit）を通過してから次の Change へ移る。`jj new` は alias で `jj-safe-new.sh` にリダイレクトされる。**（注: この実体は Issue #21 でプラグインから撤去され、現在は外部ツール jj-exec-aliases が提供する。以下は当時の記録）**
  - 性質: **安全クリティカル** かつ **個人 VCS（jj）依存**。誤った Change 切り替えを構造的に防ぐガードであり、正確性が最優先。
- **`jj-safe-push`**: jj で安全に push する唯一の方法。リモートとローカルの diverge を検知し意図しない force-push を防止する。`jj git push` の直接実行は PreToolUse hook とシェル関数ラッパーで二重にブロックされる。**（注: この実体は Issue #21 でプラグインから撤去され、現在は外部ツール jj-exec-aliases が提供する。以下は当時の記録）**
  - 性質: **安全クリティカル** かつ **個人 VCS（jj）依存**。force-push による他者の変更上書きを防ぐガードであり、正確性が最優先。
- **`my-task`（gh-my-task）**: `gh my-task` 拡張を使って自分が関わる PR の状況を一覧・分類・報告する。`rtk gh my-task -j -R` を起点に CHANGES_REQUESTED / レビュー依頼 / レビュー待ち等を優先度分類する。
  - 性質: **安全クリティカルではない**ユーティリティ。ただし `gh my-task` 拡張という外部依存を前提とする。VCS には非依存。

## 3. Issue が提示する 3 つの選択肢

| 選択肢 | 内容 |
|---|---|
| **Option A** | **dotclaude を正本**とし、プラグインは参照のみ（プラグインは実体を持たず dotclaude を指す） |
| **Option B** | **プラグインを正本**とし、dotclaude が再配布（プラグインから dotclaude へ反映） |
| **Option C** | **両方を維持**し、同期メカニズム（divergence 防止）を追加する |

## 4. 2 つのハード制約に照らした評価

評価にあたり、譲れない 2 つの制約を設定する。

### 制約 1: 配布プラグインは自己完結（self-contained）でなければならない

配布されるプラグインは、ユーザーローカルの `~/.claude` グローバルスキルに依存してはならない。
プラグインだけをインストールした他のチームメンバーが実行できなくなるためである。

→ この制約は **Option A を強く否定する**。Option A はプラグインを dotclaude（個人 `~/.claude`）への参照だけにする方針であり、
dotclaude を持たない利用者はプラグインの `jj-safe-new` / `jj-safe-push` / `my-task` を一切実行できなくなる。
リポジトリの `rules/repo-scope.md`（グローバル設定をリポジトリファイルに書かない）にも正面から反する。

### 制約 2: `jj-safe-new` / `jj-safe-push` は安全クリティカル — DRY より正確性

これらは VCS（jj）の破壊的操作（Change 境界越え・force-push）を防ぐガードである。
「重複を 1 つにまとめる（DRY）」ことよりも、**各配布先で確実に正しく動くこと（正確性）** が優先される。
正本を 1 か所に集約して参照に頼ると、参照解決の失敗がそのまま安全ガードの喪失につながる。

→ この制約は、単純な集約（Option A / Option B の「一方を消す」運用）よりも、
**両方に実体を保持しつつ divergence を防ぐ（Option C）** を支持する。

### Option ごとの結論

- **Option A（dotclaude 正本・プラグイン参照のみ）**: ✗ 不採用。制約 1 に正面衝突する。自己完結性を失う。
- **Option B（プラグイン正本・dotclaude が再配布）**: △ 自己完結性は満たすが、dotclaude 側の実体を「再配布される従属コピー」と位置づける必要があり、個人環境特有の alias / hook / シェル関数ラッパー（`jj-safe-push` の `~/.config/jj/` 連携など）を機械的に上書きすると個人セットアップを壊すリスクがある。安全クリティカルなスキルでこのリスクは取りたくない。
- **Option C（両方維持 + 同期メカニズム）**: ✓ 採用候補。自己完結性（制約 1）と正確性優先（制約 2）の両方を満たす。両者を実体として保持しつつ、CI 等で divergence を検知すればよい。

## 5. 提案決定（要ユーザー確認）

> 以下は **提案** であり、一方的・不可逆な変更ではない。確定にはユーザーの確認を要する。

| アセット | 提案 | 正本（authoritative） | 理由 |
|---|---|---|---|
| `jj-safe-new` | ~~Option C~~ → **Issue #19 で覆す** | **Skill 入口は廃止**。~~正本は実体（`scripts/jj-safe-new.sh` + hook + alias）~~ → **Issue #21 で正本を外部ツール jj-exec-aliases に移管（プラグインは jj safe-* 実体を非保持）** | 安全クリティカルだが、安全担保は元々 hook + alias 層。Skill 入口は冗長で無駄な起動を誘発していた。 |
| `jj-safe-push` | ~~Option C~~ → **Issue #19 で覆す** | **Skill 入口は廃止**。~~正本は実体（`scripts/jj-safe-push.sh` + hook + alias）~~ → **Issue #21 で正本を外部ツール jj-exec-aliases に移管（プラグインは jj safe-* 実体を非保持）** | 同上。force-push ガードは hook + alias で各配布先で動く。 |
| `gh-my-task`（`my-task`） | **Option C** | **プラグイン側コピーを正本（配布版）** | プラグインの自己完結性のため。dotclaude のコピーは個人環境用に残す。 |

### 提案の要点

- 3 アセットとも **Option C（両方維持）** を提案する。
- **プラグイン側コピーを「配布における正本（authoritative）」** と位置づける。
  チームメンバーが受け取るのはプラグインであり、プラグインが単体で完結している必要があるため。
- **dotclaude 側コピーは削除しない**。ユーザー個人の `~/.claude` グローバル環境（個人特有の alias / hook / シェル関数ラッパーを含む）として維持する。
- divergence 防止メカニズムはフォローアップとして追加する（下記チェックリスト参照）。

### この提案を選んだ根拠（DRY を捨ててでも Option C を採る理由）

「重複は悪」という一般論より、本ケースでは次の 2 点が上回る。

1. **自己完結性**: 配布プラグインが `~/.claude` を参照に行く設計は、プラグイン単独インストール者を壊す。
2. **安全ガードの可用性**: `jj-safe-*` は破壊的 VCS 操作のガード。参照解決の失敗が安全機能の喪失に直結するため、各配布先に実体を持つことが望ましい。

重複によるメンテナンスコストは、CI の diff チェック（後述）で divergence を機械検知することで実用上吸収できる。

## 6. フォローアップ dedup チェックリスト

以下はこの方針を確定したあとに実施するフォローアップ作業。

- [ ] **(a) 同期メカニズムの選定** — 候補を比較し 1 つ選ぶ。**推奨: CI `diff` チェック**。
  - 候補比較:
    - **CI `diff` チェック（推奨）**: CI 上で dotclaude 側と プラグイン側の該当 `SKILL.md` を `diff` し、差分があれば fail させて divergence を検知する。実体は両側に残るため自己完結性を損なわず、安全クリティカルなスキルでも正確性を担保しやすい。
    - **symlink**: 片方を実体、もう片方をシンボリックリンクにする。配布時にリンクが解決できない環境（プラグイン単独配布）で壊れるため、自己完結性の観点で不適。
    - **手動同期（ドキュメント化のみ）**: 運用手順書化するだけ。属人化し divergence を見逃しやすいため次善。
- [ ] **(b) フォローアップ Issue の作成** — (a) で選んだ dedup / 同期メカニズムを実装する Issue を起票する（本 Issue #11 はあくまで方針の決定・記録に限定し、実装は分離する）。
- [ ] **(c) dotclaude 側での決定のミラー** — 本方針（プラグイン側を配布の正本とし、dotclaude は個人グローバルコピーとして維持する）を dotclaude リポジトリ側にも記録し、両リポジトリで認識を揃える。

## 7. 関連ルール

- `rules/repo-scope.md`: グローバル設定（`~/.claude`）をリポジトリファイルに書かない。プラグインのコマンドが依存するスキルはリポジトリ内に存在させる。
- `rules/agent-skill-architecture.md`: `jj-safe-new` / `jj-safe-push` は L2（安全クリティカル）として分類。**当初は `disable-model-invocation` の Skill 入口を維持する方針だったが、Issue #19 で Skill 入口を廃止**し、安全担保は hook + alias 層に一本化した（破壊的操作の入口を Skill として持たない）。

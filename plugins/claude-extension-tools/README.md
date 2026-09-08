# claude-extension-tools

Claude CodeのSkill、Subagent、Rules、Hooks、Pluginを作成・レビューするためのPluginです。

## 使い方

`claude-extension-tools:claude-extension-authoring` Skillを使うと、対象の種類を選び、frontmatter、権限、参照資料、補助スクリプト、検証方法を含む構成を作成できます。

作成後は`claude-extension-tools:claude-extension-reviewer` Subagentへ対象パスを渡します。このSubagentは作成Skillをfrontmatterの`skills`からプリロードし、構造検証、公式仕様、最小権限、コンテキスト効率、Hookの決定性、根拠とテストを読み取り専用で確認します。

```text
/claude-extension-tools:claude-extension-authoring plugins/example/skills/example

claude-extension-tools:claude-extension-reviewerで plugins/example/skills/example と関連するPlugin設定をレビューしてください。
```

## 決定的な検証

```bash
python3 plugins/claude-extension-tools/scripts/validate_extension.py \
  plugins/claude-extension-tools/skills/claude-extension-authoring

python3 plugins/claude-extension-tools/scripts/validate_extension.py \
  plugins/claude-extension-tools/agents/claude-extension-reviewer.md

python3 -m unittest discover \
  -s plugins/claude-extension-tools/scripts -p 'test_*.py'
```

公式仕様へのリンクと、Skill本文へ置く内容と参照資料へ分ける内容の基準は、`skills/claude-extension-authoring/references/official-guidance.md`にあります。

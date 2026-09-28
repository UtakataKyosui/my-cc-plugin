---
name: markdown-new
description: URL のページを Markdown の全文で取得してファイルに保存する。WebFetch は小さいモデルが prompt に答えた結果しか返さないため、ページ全体を読みたいとき、保存して grep したいとき、WebFetch の結果に抜けがありそうなときに使う。対象サイトが Markdown を返せば直接取り、返さなければ第三者の変換サービス markdown.new で変換する。「このページを Markdown で取って」「記事の全文を保存して」「WebFetch だと内容が欠ける」と言われたときに使う。
---

# markdown-new

WebFetch はページを Markdown に変換したあと、小さいモデルに prompt を当てた答えだけを Claude に返す（公式の tools-reference の「WebFetch tool behavior」）。このスキルは curl で取得した Markdown をそのままファイルに書くので、要約を通らない。

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/markdown-new/fetch.sh https://blog.cloudflare.com/markdown-for-agents/
```

`CLAUDE_PLUGIN_ROOT` はこのプラグインがインストールされたディレクトリを指す。手動で実行するときの実パスは `claude plugin list --json` で確認するか、`find ~/.claude/plugins -path '*/markdown-new/skills/markdown-new/fetch.sh'` で探す。

```
path: /var/folders/.../T/markdown-new/blog.cloudflare.com-1221610912.md
source: direct（対象サイトが Markdown を返した）
lines: 248
bytes: 18240
tokens: 不明
```

`path` を Read で読む。`source` が `markdown.new` のときは、括弧の中に markdown.new が使った変換方式が入る。

| オプション | 意味 |
|---|---|
| `--method auto\|ai\|browser` | `auto` は直接取得を試してから markdown.new に回す。`ai` と `browser` は直接取得を飛ばし、markdown.new の変換方式を指定する。JS で本文を組み立てるページは `browser` にする |
| `--images` | markdown.new の変換結果に画像を残す |
| `--no-relay` | markdown.new に送らない。対象サイトから直接取れたときだけ保存する |
| `--out <path>` | 保存先。省略すると `$TMPDIR/markdown-new/<ホスト>-<URL のハッシュ>.md` に書く |

## 取得の順番と、markdown.new に送らない条件

最初に `Accept: text/markdown, text/html;q=0.9` を付けて対象サイトから直接取る。状態コードが 2xx で、Content-Type が `text/markdown` で、本文が空でなければそれを保存する。Cloudflare の Markdown for Agents を有効にしたサイトはここで取れる。

直接取れなければ、markdown.new の POST API に URL を送って変換させる。ただし次のどれかに当たる URL は送らず、終了コード 3 で止まる。

- `--no-relay` か `MDNEW_NO_RELAY=1` が指定されている
- URL に `user:pass@` のようなユーザー情報が入っている
- ホストが外から届かない。localhost、ドットの無いホスト名、`.local`・`.internal`・`.lan`・`.home.arpa`、127/8・10/8・172.16/12・192.168/16・169.254/16、IPv6 のリテラル
- クエリの引数名が認証情報に見える。`token`・`secret`・`signature`・`password`・`credential`・`apikey`・`jwt` で終わる名前がこれに当たる。`key`・`sig`・`code`・`sid`・`auth`・`session`・`otp`・`pwd` は、名前全体がそれか、`_` `-` `.` の後ろに付くときだけ当たる（`access_token`、`X-Amz-Signature`、`api_key` など）

URL のフラグメント（`#` 以降）は、直接取得でも markdown.new でも送る前に落とす。パスの中に入った秘密（`/reset/<token>` のような形）は見分けられない。

## 関数

`fetch.sh` は `lib/markdown-new.sh` を source する薄い CLI である。他のスクリプトから使うときは lib を直接読む。lib は bash の配列と `[[ =~ ]]` を使うので、zsh から source せず `bash -c` の中で読み込む。場所は `MDNEW_LIB` で差し替えられる（既定値はスクリプトから見た相対パス `lib/markdown-new.sh`）。

```bash
bash -c 'source "${MDNEW_LIB:-'"${CLAUDE_PLUGIN_ROOT}"'/skills/markdown-new/lib/markdown-new.sh}"; mdnew_fetch https://example.com/ /tmp/ex.md && echo "$MDNEW_SOURCE $MDNEW_DETAIL"'
```

| 関数 | 役割 |
|---|---|
| `mdnew_fetch <url> <out> [method] [retain_images]` | 直接取得を試し、だめなら markdown.new で変換して `out` に書く。失敗したら理由を stderr に出し、`out` を残さない |
| `mdnew_fetch_direct <url> <out>` | 対象サイトから直接取る。Markdown が返らなければ 1 を返す |
| `mdnew_fetch_relay <url> <out> [method] [retain_images]` | markdown.new の POST API で変換する。送ってよいかは確かめないので、先に `mdnew_relay_allowed` を通す |
| `mdnew_relay_allowed <url>` | markdown.new に送ってよければ 0 を返す。だめなら理由を stdout に出して 1 を返す |
| `mdnew_default_path <url>` | 既定の保存先を出力する。`MDNEW_OUT_DIR` で親ディレクトリを変えられる |

取得の結果は `MDNEW_SOURCE`（`direct` か `markdown.new`）、`MDNEW_DETAIL`（取得元の説明か失敗の理由）、`MDNEW_TOKENS`（推定トークン数。無ければ空）に入る。

| 終了コード | 意味 |
|---|---|
| 0 | 保存した |
| 2 | 引数が正しくない。URL が http でも https でもない、`method` や `retain_images` の値が違う |
| 3 | 直接は取れず、上の条件に当たったので markdown.new に送らなかった |
| 4 | markdown.new でも変換できなかった |
| 5 | markdown.new のレート制限（HTTP 429）に当たった |
| 1 | 一時ファイルや保存先のディレクトリを作れなかった |

## 実測で分かった罠

2026-09-28 に markdown.new と Cloudflare のサイトで確かめた挙動である。markdown.new の仕様が変わった気配があれば `bash ${CLAUDE_PLUGIN_ROOT}/skills/markdown-new/selftest.sh` を実行する。selftest は markdown.new に 3 回送る。`MDNEW_SELFTEST_OFFLINE=1` を付けるとネットワーク越しの確認を飛ばす。

GET 形式の `https://markdown.new/<url>` は、対象 URL のクエリを落とす。`https://markdown.new/https://httpbin.org/anything?foo=bar` を取ると、httpbin が受け取った `args` は空で、応答の `URL Source:` にもクエリが無かった。POST で `{"url": "..."}` を送ればクエリは保たれる。lib は POST だけを使う。

GET 形式はスキームの無いパスをドメインとして読む。`https://markdown.new/SKILL.md` は `https://SKILL.md` を変換した別サイトの内容を返した。POST も `{"url": "example.com"}` を拒否せずに変換する。lib は http か https で始まる URL だけを受け付ける。

POST の応答は JSON で、成功すると `success`・`url`・`title`・`content`・`timestamp`・`method`・`duration_ms` が入る。`tokens` は Workers AI で変換した example.com には付き、Markdown for Agents と Browser Rendering で変換したときには付かなかった。`method` の値は `Cloudflare Markdown for Agents`・`Cloudflare Workers AI`・`Cloudflare Browser Rendering` の 3 種類を見た。example.com の変換にかかった時間は、Workers AI が 80 ms、Browser Rendering が 1844 ms だった。

変換できなかったときは HTTP 500 と `{"success":false,"error":"..."}` が返る。FAQ にある `x-rate-limit-remaining` ヘッダーは、成功した応答に付いていなかった。429 は試していない。FAQ の「IP ごとに 1 日 500 回、超えたら 429」に合わせて扱っている。

Workers AI の変換は本文の `_` を `\_` にエスケープする。httpbin の `mdnew_probe` は `mdnew\_probe` になった。保存したファイルを grep するときは `\_` になっている場合を含めて探す。

Accept を無視して HTML を 200 で返すサイトは多い。example.com は `Accept: text/markdown` を付けても `text/html` を返した。直接取得の成否は状態コードではなく Content-Type で決める。

Cloudflare のブログは、Markdown for Agents の応答に `x-markdown-tokens` が付くと書いている。blog.cloudflare.com と developers.cloudflare.com から直接取った応答には付いておらず、`content-signal` だけがあった。直接取得では `tokens: 不明` になることが多い。

markdown.new が対象サイトへ送るヘッダーは `Accept: text/markdown, text/html;q=0.9` と `User-Agent: markdown.new/1.0` だった（httpbin の `headers` で確認）。直接取得の Accept はこれに揃えている。サイトが `robots.txt` やサーバーの設定で `markdown.new` を拒否していると、markdown.new 経由では取れない。

bash 5.3 では、`"HTTP $code、..."` のように変数の直後に全角文字を置くと、全角文字のバイトまで変数名として読まれ、`code�: unbound variable` で止まる。lib を直すときは `${code}、` のように波括弧で囲む。

## markdown.new について

markdown.new は Cloudflare の公式サービスではない。サイトのフッターには「Made by Emre Elbeyoglu」とあり、Privacy Policy の運営者は ScrapingAPI Ltd である。2026-09-28 時点の Privacy Policy では、変換結果を 5 分、レート制限のための IP アドレスを最大 2 日保存する。Terms of Use では、サービスの提供に必要な範囲で内容を処理・保存するライセンスを利用者が与えることになっている。社外秘の URL は `--no-relay` を付けて取る。

## 依存

bash、curl、jq、cksum、mktemp、awk、tr、paste を使う。一時ファイルは mktemp で作り、使い終わったら消す。selftest は blog.cloudflare.com、example.com、httpbin.org、markdown.new に接続する。

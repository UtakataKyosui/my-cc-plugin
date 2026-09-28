// classic.* が実際に運ぶフィールドと、watchPaths のファイル監視を確かめる。
// これらは claude plugin test では検証できない（ハーネスが engine 自身の
// ステップを持たないため、prompt.submit を next なしで答えた時点で降りない）。
import type { Register } from "claude-code";

const OUT = "__OUT__";
const WATCH = "__OUT__.watched";
const seen: string[] = [];

async function note($: { fs: { write: (p: string, t: string) => Promise<void> } }, line: string) {
  seen.push(line);
  await $.fs.write(OUT, seen.join("\n") + "\n");
}

export const register: Register = (on) => {
  on("classic.SessionStart", async ($, e, next) => {
    const result = await next(e);
    await note($, `SessionStart keys=${Object.keys(e).join(",")}`);
    return { ...result, watchPaths: [...(result.watchPaths ?? []), WATCH] };
  });
  on("classic.UserPromptSubmit", async ($, e, next) => {
    await note($, `UserPromptSubmit session_id=${e.session_id} prompt_id=${e.prompt_id ?? "(none)"}`);
    return next(e);
  });
  on("classic.FileChanged", async ($, e, next) => {
    await note($, `FileChanged path=${e.file_path} event=${e.event}`);
    return next(e);
  });
};

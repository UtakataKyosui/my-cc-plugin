// 最初のユーザーメッセージに載る attachment を全部列挙する。
// Skill 一覧と SubAgent 一覧はここに居る（prompt.section ではない）。
import type { Register } from "claude-code";

const OUT = "__OUT__";
const seen: string[] = [];

export const register: Register = (on) => {
  on("prompt.attachment", async ($, e, next) => {
    const result = await next(e);
    const text = result.text ?? "";
    seen.push(`type=${e.type} chars=${text.length}\n  head=${text.slice(0, 160).replace(/\n/g, "\\n")}`);
    await $.fs.write(OUT, seen.join("\n") + "\n");
    return result;
  });
};

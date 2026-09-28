// システムプロンプトのセクション名を列挙する。engine は名前を型定義に
// 列挙していないため、書き換えたいセクションはここで名前を確かめる。
import type { Register } from "claude-code";

const OUT = "__OUT__";
const seen: string[] = [];

export const register: Register = (on) => {
  on("prompt.section", async ($, e, next) => {
    const result = await next(e);
    seen.push(`${e.name}\tchars=${result.text?.length ?? 0}`);
    await $.fs.write(OUT, seen.join("\n") + "\n");
    return result;
  });
};

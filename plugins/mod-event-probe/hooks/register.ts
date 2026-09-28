import type { On } from "claude-code";
const LOG = "/tmp/mod-event-probe.jsonl";
let buf = "";
async function log($: any, obj: unknown) {
  buf += JSON.stringify(obj) + "\n";
  try { await $.fs.write(LOG, buf); } catch (err) { buf += JSON.stringify({ writeErr: String(err) }) + "\n"; }
}
// MOD_PROBE_SINK が設定されていれば、各イベントをその URL にも POST して $.http.fetch の到達性を確かめる
async function post($: any, obj: unknown) {
  const sink = await $.env.get("MOD_PROBE_SINK");
  if (!sink) return;
  try {
    const r = await $.http.fetch(sink, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(obj) });
    if (!r.ok) await log($, { ev: "post.fail", status: r.status });
  } catch (err) {
    await log($, { ev: "post.error", error: String(err) });
  }
}
async function record($: any, obj: unknown) {
  await log($, obj);
  await post($, obj);
}
export function register(on: On) {
  on("session.start", async ($, e, next) => {
    await record($, { ev: "session.start", taskId: (await $.env.get("MOD_PROBE_TASK_ID")) ?? null });
    return next(e);
  });
  on("agent.spawn", async ($, e, next) => {
    await record($, { ev: "agent.spawn", subagentType: e.subagentType, provider: e.provider, description: e.description, fork: e.fork, model: e.model, parentAgentId: (e as any).parentAgentId, prompt: e.prompt.slice(0, 80) });
    const r = await next(e);
    await record($, { ev: "agent.spawn.result", agentId: r.agentId });
    return r;
  });
  on("skill.prompt", async ($, e, next) => {
    await record($, { ev: "skill.prompt", keys: Object.keys(e ?? {}), skill: (e as any)?.skill, textType: typeof (e as any)?.text });
    return next(e);
  });
  on("tool.call", async ($, e, next) => {
    if (e.tool === "Skill" || e.tool === "Agent") {
      await record($, { ev: "tool.call", tool: e.tool, agentId: (e as any).agentId, skill: (e as any).skill, subagent_type: (e as any).subagent_type });
    }
    return next(e);
  });
  on("turn.step", async function* ($, e, next) {
    const listed = e.agentId ? (await $.agent.list()).some((a) => a.id === e.agentId) : null;
    await record($, { ev: "turn.step", agentId: e.agentId, index: e.index, model: e.model, effort: e.effort, messageCount: e.messageCount, listed });
    return yield* next(e);
  });
}

// Owned by shared-memory-vault; does not require Agent Overlay.
import { spawn } from "node:child_process"
const run = (args: string[], input: unknown) => new Promise<string>((resolve) => {
  const child = spawn("__PYTHON__", ["-m", "agent_memory.adapters.common", ...args], { stdio: ["pipe", "pipe", "ignore"] })
  let output = ""; child.stdout.on("data", (chunk) => output += chunk)
  child.on("error", () => resolve("")); child.on("close", () => resolve(output.trim()))
  child.stdin.end(JSON.stringify(input))
})
export default function (pi: any) {
  pi.on("before_agent_start", async (event: any) => {
    const content = await run(["recall"], { prompt: event.prompt })
    if (content) return { message: { customType: "shared-memory-recall", content, display: false } }
  })
  pi.on("session_shutdown", async (_event: any, ctx: any) => {
    try {
      const prompts: string[] = [], commands: string[] = [], files = new Set<string>(); let final_response = ""
      for (const entry of ctx.sessionManager.getBranch() || []) {
        const message = entry.message; if (!message) continue
        const parts = typeof message.content === "string" ? [{ type: "text", text: message.content }] : message.content || []
        const text = parts.filter((p: any) => p.type === "text").map((p: any) => p.text).join("\n")
        if (message.role === "user") prompts.push(text); else if (message.role === "assistant" && text) final_response = text
        for (const part of parts) if (part.type === "toolCall") {
          if (part.arguments?.command) commands.push(String(part.arguments.command).split("\n")[0])
          if (part.arguments?.path) files.add(part.arguments.path)
        }
      }
      void run(["capture", "pi"], { session_id: ctx.sessionManager.getSessionId(), cwd: ctx.cwd, prompts, commands, files_changed: [...files], final_response })
    } catch {}
  })
}

// Owned by shared-memory-vault; coexists with unrelated OpenCode plugins.
import { spawn } from "node:child_process"

const run = (args: string[], input: unknown) => new Promise<string>((resolve) => {
  const child = spawn("__PYTHON__", ["-m", "agent_memory.adapters.common", ...args], { stdio: ["pipe", "pipe", "ignore"] })
  let output = ""
  child.stdout.on("data", (chunk) => output += chunk)
  child.on("error", () => resolve(""))
  child.on("close", () => resolve(output.trim()))
  child.stdin.end(JSON.stringify(input))
})

const pending = new Map<string, string>()
export const SharedMemory = async ({ client, directory }: any) => ({
  "chat.message": async ({ sessionID }: any, output: any) => {
    const text = (output.parts || []).filter((p: any) => p.type === "text").map((p: any) => p.text).join("\n")
    pending.set(sessionID, await run(["recall"], { prompt: text }))
  },
  "experimental.chat.system.transform": async ({ sessionID }: any, output: any) => {
    const context = pending.get(sessionID); pending.delete(sessionID)
    if (context) output.system.push(context)
  },
  event: async ({ event }: any) => {
    if (event.type !== "session.idle") return
    try {
      const id = event.properties?.sessionID
      const session = await client.session.get({ path: { id } })
      const messages = await client.session.messages({ path: { id } })
      const prompts: string[] = [], files = new Set<string>(), commands: string[] = []
      let final_response = ""
      for (const message of messages.data || []) {
        const parts = message.parts || []
        if (message.info?.role === "user") prompts.push(parts.filter((p: any) => p.type === "text").map((p: any) => p.text).join("\n"))
        if (message.info?.role === "assistant") final_response = parts.filter((p: any) => p.type === "text").map((p: any) => p.text).join("\n") || final_response
        for (const part of parts) if (part.type === "tool" && part.state?.input?.command) commands.push(String(part.state.input.command).split("\n")[0])
      }
      const diff = await client.session.diff({ path: { id } })
      for (const item of diff.data || []) if (item.file) files.add(item.file)
      void run(["capture", "opencode"], { session_id: id, cwd: session.data?.directory || directory, prompts, commands, files_changed: [...files], final_response })
    } catch {}
  },
})
export default SharedMemory

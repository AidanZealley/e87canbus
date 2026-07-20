import { readFile, writeFile } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import { compileFromFile } from "json-schema-to-typescript"

const root = fileURLToPath(new URL("../..", import.meta.url))
const schema = `${root}/protocol/live-events-v1.schema.json`
const output = fileURLToPath(
  new URL("../src/api/live-contract.gen.ts", import.meta.url)
)
const check = process.argv.includes("--check")
const schemaDocument = JSON.parse(await readFile(schema, "utf8"))

const generated = await compileFromFile(schema, {
  bannerComment:
    "/** Generated from protocol/live-events-v1.schema.json. Do not edit. */",
  // Avoid expanding wide bounded arrays into a union of every possible tuple
  // length. Exact fixed-size tuples, such as 16-byte commands, are preserved.
  maxItems: 10,
  style: { semi: false, singleQuote: false, tabWidth: 2, trailingComma: "all" },
})

const bridge = `
export const LIVE_PROTOCOL_VERSION = ${schemaDocument.properties.protocol_version.const} as const

type SocketEvent = { event: string; args: unknown[] }

type SocketEventMap<Event extends SocketEvent> = {
  [Name in Event["event"]]: (
    ...args: Extract<Event, { event: Name }>["args"]
  ) => void
}

export type ServerToClientEvents = SocketEventMap<ServerToClientEvent>
export type ClientToServerEvents = SocketEventMap<ClientToServerEvent>
export type ServerEventPayload<Name extends keyof ServerToClientEvents> =
  Parameters<ServerToClientEvents[Name]>[0]
`
const expected = `${generated.trimEnd()}\n${bridge}`

if (check) {
  const current = await readFile(output, "utf8").catch(() => "")
  if (current !== expected) {
    console.error(`generated live TypeScript contract is stale: ${output}`)
    process.exitCode = 1
  }
} else {
  await writeFile(output, expected)
}

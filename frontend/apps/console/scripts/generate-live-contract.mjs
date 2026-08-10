import { readFile, writeFile } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import { compileFromFile } from "json-schema-to-typescript"

const root = fileURLToPath(new URL("../../../..", import.meta.url))
const schema = `${root}/protocol/console-live-v1.schema.json`
const output = fileURLToPath(
  new URL("../src/local-live/contract.gen.ts", import.meta.url)
)
const check = process.argv.includes("--check")
const schemaDocument = JSON.parse(await readFile(schema, "utf8"))

const generated = await compileFromFile(schema, {
  bannerComment:
    "/** Generated from protocol/console-live-v1.schema.json. Do not edit. */",
  style: { semi: false, singleQuote: false, tabWidth: 2, trailingComma: "all" },
})

const bridge = `
export const CONSOLE_PROTOCOL_VERSION = ${schemaDocument.properties.protocol_version.const} as const

type SocketEvent = { event: string; args: unknown[] }
type SocketEventMap<Event extends SocketEvent> = {
  [Name in Event["event"]]: (
    ...args: Extract<Event, { event: Name }>["args"]
  ) => void
}

export type ConsoleServerEvents = SocketEventMap<ConsoleSnapshotEvent>
export type ConsoleSnapshotPayload = Parameters<
  ConsoleServerEvents["console.snapshot"]
>[0]
`
const expected = `${generated.trimEnd()}\n${bridge}`

if (check) {
  const current = await readFile(output, "utf8").catch(() => "")
  if (current !== expected) {
    console.error(`generated console TypeScript contract is stale: ${output}`)
    process.exitCode = 1
  }
} else {
  await writeFile(output, expected)
}

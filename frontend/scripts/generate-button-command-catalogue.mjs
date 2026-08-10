import { readFile, writeFile } from "node:fs/promises"
import { format } from "prettier"

const input = new URL("../../protocol/openapi.json", import.meta.url)
const output = new URL(
  "../packages/coordinator-client/src/api/button-command-catalogue.gen.ts",
  import.meta.url
)
const check = process.argv.includes("--check")

const schema = JSON.parse(await readFile(input, "utf8"))
const commandProperty =
  schema.components.schemas.ButtonProfileSlotRequest.properties.command
const entries = schema["x-button-command-catalogue"]

if (!Array.isArray(entries)) {
  throw new Error("OpenAPI schema has no x-button-command-catalogue extension")
}

const referenceForType = commandProperty.discriminator.mapping
const catalogue = entries.map((entry) => {
  const reference = referenceForType[entry.type]
  if (typeof reference !== "string") {
    throw new Error(`No command schema for ${entry.type}`)
  }
  const schemaName = reference.split("/").at(-1)
  const commandSchema = schema.components.schemas[schemaName]
  const fields = Object.entries(commandSchema.properties)
    .filter(([name]) => name !== "type")
    .map(([name, property]) => {
      const common = { name, label: property.title ?? name }
      if (Array.isArray(property.enum)) {
        return { ...common, kind: "enum", values: property.enum }
      }
      if (property.type === "boolean") {
        return { ...common, kind: "boolean" }
      }
      if (property.type === "integer") {
        return {
          ...common,
          kind: "integer",
          ...(property.minimum === undefined
            ? {}
            : { minimum: property.minimum }),
          ...(property.maximum === undefined
            ? {}
            : { maximum: property.maximum }),
        }
      }
      throw new Error(
        `Unsupported field schema for ${entry.type}.${name}: ${property.type}`
      )
    })
  return {
    type: entry.type,
    hasActiveState: entry.has_active_state,
    fields,
  }
})

const rendered = await format(
  `// This file is auto-generated from protocol/openapi.json.
// Run \`pnpm http:generate\` after changing the backend button catalogue.

export type ButtonCommandFieldSpec =
  | {
      readonly name: string
      readonly label: string
      readonly kind: "enum"
      readonly values: readonly (string | number)[]
    }
  | {
      readonly name: string
      readonly label: string
      readonly kind: "boolean"
    }
  | {
      readonly name: string
      readonly label: string
      readonly kind: "integer"
      readonly minimum?: number
      readonly maximum?: number
    }

export type ButtonCommandSpec = {
  readonly type: string
  readonly hasActiveState: boolean
  readonly fields: readonly ButtonCommandFieldSpec[]
}

export const BUTTON_COMMAND_CATALOGUE = ${JSON.stringify(catalogue, null, 2)} as const satisfies readonly ButtonCommandSpec[]
`,
  { parser: "typescript" }
)

if (check) {
  const current = await readFile(output, "utf8").catch(() => "")
  if (current !== rendered) {
    console.error(
      `generated button command catalogue is stale: ${output.pathname}`
    )
    process.exitCode = 1
  }
} else {
  await writeFile(output, rendered)
}

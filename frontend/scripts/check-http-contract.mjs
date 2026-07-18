import { execFile } from "node:child_process"
import { readdir, readFile, rm } from "node:fs/promises"
import { promisify } from "node:util"

const run = promisify(execFile)
const generatedDirectory = new URL("../src/api/http/", import.meta.url)
const checkDirectory = new URL("../src/api/http.check/", import.meta.url)

const readTree = async (directory, prefix = "") => {
  const files = new Map()
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relativePath = `${prefix}${entry.name}`
    if (entry.isDirectory()) {
      const nested = await readTree(
        new URL(`${entry.name}/`, directory),
        `${relativePath}/`
      )
      for (const file of nested) files.set(...file)
    } else {
      files.set(relativePath, await readFile(new URL(entry.name, directory)))
    }
  }
  return files
}

await rm(checkDirectory, { force: true, recursive: true })
try {
  await run("pnpm", ["exec", "openapi-ts", "-o", "src/api/http.check"])
  await run("pnpm", [
    "exec",
    "prettier",
    "--write",
    "src/api/http.check/**/*.ts",
  ])

  const [generated, expected] = await Promise.all([
    readTree(generatedDirectory),
    readTree(checkDirectory),
  ])
  const paths = new Set([...generated.keys(), ...expected.keys()])
  const stale = [...paths].filter(
    (path) => !generated.get(path)?.equals(expected.get(path))
  )
  if (stale.length > 0) {
    console.error(`generated HTTP client is stale:\n${stale.join("\n")}`)
    process.exitCode = 1
  }
} finally {
  await rm(checkDirectory, { force: true, recursive: true })
}

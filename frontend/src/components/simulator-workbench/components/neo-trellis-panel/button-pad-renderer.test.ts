import { describe, expect, it } from "vitest"

import vectorsJson from "../../../../../../protocol/test-vectors/button-pad-program-v2.json"
import { typescriptButtonPadRenderer } from "./button-pad-renderer"

type ProgramVector = {
  name: string
  commands_hex: string[]
  frames: { elapsed_ms: number; animation_mask: number; rgb_hex: string }[]
}
type InvalidVector = { name: string; payload_hex: string }
const vectors = vectorsJson as {
  programs: ProgramVector[]
  invalid_commands: InvalidVector[]
}

const fromHex = (hex: string) =>
  Uint8Array.from(
    hex.match(/.{2}/g)?.map((byte) => Number.parseInt(byte, 16)) ?? []
  )
const frameHex = (frame: readonly (readonly number[])[]) =>
  frame
    .flatMap((rgb) => [...rgb])
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("")

describe("typescriptButtonPadRenderer conformance", () => {
  for (const vector of vectors.programs) {
    it(`renders ${vector.name}`, () => {
      const commands = vector.commands_hex.map(fromHex)
      const state = typescriptButtonPadRenderer.createState(commands, 0, null)
      expect(state).not.toBeNull()
      for (const expected of vector.frames) {
        const rendered = typescriptButtonPadRenderer.render(
          state,
          expected.elapsed_ms
        )
        expect(rendered, `frame at ${expected.elapsed_ms}ms`).not.toBeNull()
        expect(rendered?.animationMask).toBe(expected.animation_mask)
        expect(frameHex(rendered?.frame ?? [])).toBe(expected.rgb_hex)
      }
    })
  }

  it("retains the phase of an unchanged track across another button update", () => {
    const vector = vectors.programs[0]
    const commands = vector.commands_hex.map(fromHex)
    const initial = typescriptButtonPadRenderer.createState(commands, 0, null)
    const updatedCommands = commands.map((command) => Uint8Array.from(command))
    updatedCommands[0][5] = 0x20
    const updated = typescriptButtonPadRenderer.createState(
      updatedCommands,
      400,
      initial
    )

    const rendered = typescriptButtonPadRenderer.render(updated, 800)
    expect(rendered?.frame[15]).toEqual([0, 220, 255])
  })

  for (const vector of vectors.invalid_commands) {
    it(`rejects ${vector.name}`, () => {
      expect(
        typescriptButtonPadRenderer.createState(
          [fromHex(vector.payload_hex)],
          0,
          null
        )
      ).toBeNull()
    })
  }
})

import { useEffect, useMemo, useRef, useState } from "react"

import type {
  ButtonPadRender,
  ButtonPadRenderer,
} from "@/components/simulator-workbench/components/neo-trellis-panel/button-pad-renderer"

type ButtonPadProgram = {
  generation: number
  commands: readonly (readonly number[])[]
}

export const useButtonPadProgram = (
  renderer: ButtonPadRenderer,
  program: ButtonPadProgram,
  active: boolean
): ButtonPadRender | null => {
  const commands = useMemo(
    () => program.commands.map((command) => Uint8Array.from(command)),
    [program.commands]
  )
  const previous = useRef<unknown>(null)
  const key = `${program.generation}:${active}`
  const [rendered, setRendered] = useState<{
    key: string
    value: ButtonPadRender | null
  } | null>(null)

  useEffect(() => {
    if (!active) {
      return
    }
    const now = performance.now()
    const state = renderer.createState(commands, now, previous.current)
    if (state === null) {
      return
    }
    previous.current = state
    const initial = renderer.render(state, now)
    setRendered({ key, value: initial })
    if (initial?.animationMask === 0) return

    let frame = 0
    const animate = (animationNow: number) => {
      const value = renderer.render(state, animationNow)
      setRendered({ key, value })
      if (value !== null && value.animationMask !== 0)
        frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [active, commands, key, renderer])

  // A new program is rendered from an effect. Retain the previous frame during
  // that one-render hand-off rather than briefly displaying all LEDs as black.
  return active ? (rendered?.value ?? null) : null
}

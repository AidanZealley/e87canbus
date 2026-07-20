export type Rgb = readonly [number, number, number]
export type ButtonPadFrame = readonly Rgb[]
export type ButtonPadRender = {
  frame: ButtonPadFrame
  animationMask: number
}

export interface ButtonPadRenderer {
  createState(
    commands: readonly Uint8Array[],
    nowMs: number,
    previous: unknown | null
  ): unknown | null
  render(state: unknown, nowMs: number): ButtonPadRender | null
}

const VERSION = 2
const REPLACE_ALL = 1
const SET_TRACK = 2
const COMMIT = 0x80
const SOLID = 1
const BLINK = 2
const BREATHE = 3
const TRAVELLING_GRADIENT = 4
const GRADIENT_NORTH_WEST_TO_SOUTH_EAST = 1
const LED_COUNT = 16
const COMMAND_LENGTH = 16

type Track = {
  kind: number
  rgb: Rgb
  parameterA: number
  parameterB: number
  repeat: number
  finalRgb: Rgb
}

type RendererState = {
  tracks: Track[]
  startedAt: number[]
}

const sameTrack = (left: Track, right: Track) =>
  left.kind === right.kind &&
  left.parameterA === right.parameterA &&
  left.parameterB === right.parameterB &&
  left.repeat === right.repeat &&
  left.rgb.every((value, index) => value === right.rgb[index]) &&
  left.finalRgb.every((value, index) => value === right.finalRgb[index])

const decode = (
  command: Uint8Array
): { mask: number; replaceAll: boolean; commit: boolean; track: Track } | null => {
  const opcode = command[1] & ~COMMIT
  if (
    command.length !== COMMAND_LENGTH ||
    command[0] !== VERSION ||
    (opcode !== REPLACE_ALL && opcode !== SET_TRACK)
  )
    return null
  const mask = command[2] | (command[3] << 8)
  const track: Track = {
    kind: command[4],
    rgb: [command[5], command[6], command[7]],
    parameterA: command[8] | (command[9] << 8),
    parameterB: command[10] | (command[11] << 8),
    repeat: command[12],
    finalRgb: [command[13], command[14], command[15]],
  }
  const minimum = track.parameterB & 0xff
  const maximum = track.parameterB >> 8
  const valid =
    mask !== 0 &&
    ((track.kind === SOLID &&
      track.parameterA === 0 &&
      track.parameterB === 0 &&
      track.repeat === 0) ||
      (track.kind === BLINK &&
        track.parameterA >= 1 &&
        track.parameterA <= 10_000 &&
        track.parameterB >= 1 &&
        track.parameterB <= 10_000) ||
      (track.kind === BREATHE &&
        track.parameterA >= 250 &&
        track.parameterA <= 10_000 &&
        minimum <= maximum) ||
      (track.kind === TRAVELLING_GRADIENT &&
        track.parameterA >= 250 &&
        track.parameterA <= 10_000 &&
        track.parameterB === GRADIENT_NORTH_WEST_TO_SOUTH_EAST))
  return valid
    ? {
        mask,
        replaceAll: opcode === REPLACE_ALL,
        commit: (command[1] & COMMIT) !== 0,
        track,
      }
    : null
}

const renderTrack = (
  track: Track,
  index: number,
  elapsedMs: number
): { rgb: Rgb; animated: boolean } => {
  if (track.kind === SOLID) return { rgb: track.rgb, animated: false }
  const cycle =
    track.kind === BLINK
      ? track.parameterA + track.parameterB
      : track.parameterA
  if (track.repeat !== 0 && elapsedMs >= cycle * track.repeat) {
    return { rgb: track.finalRgb, animated: false }
  }
  const phase = Math.floor(elapsedMs) % cycle
  if (track.kind === BLINK) {
    return {
      rgb: phase < track.parameterA ? track.rgb : track.finalRgb,
      animated: true,
    }
  }
  if (track.kind === TRAVELLING_GRADIENT) {
    const timePhase = Math.floor(
      ((Math.floor(elapsedMs) % track.parameterA) * 256) / track.parameterA
    )
    const row = Math.floor(index / 4)
    const column = index % 4
    const position = (timePhase + ((row + column) * 256) / 6) & 0xff
    const blend = position <= 128 ? position * 2 : (256 - position) * 2
    return {
      rgb: [0, 1, 2].map(
        (channel) =>
          track.rgb[channel] +
          Math.trunc(((track.finalRgb[channel] - track.rgb[channel]) * blend) / 256)
      ) as Rgb,
      animated: true,
    }
  }
  const halfPeriod = Math.floor(track.parameterA / 2)
  const triangle =
    phase <= halfPeriod
      ? Math.floor((phase * 255) / halfPeriod)
      : Math.floor(
          ((track.parameterA - phase) * 255) / (track.parameterA - halfPeriod)
        )
  const minimum = track.parameterB & 0xff
  const maximum = track.parameterB >> 8
  const brightness =
    minimum + Math.floor(((maximum - minimum) * triangle) / 255)
  return {
    rgb: [
      Math.floor((track.rgb[0] * brightness) / 255),
      Math.floor((track.rgb[1] * brightness) / 255),
      Math.floor((track.rgb[2] * brightness) / 255),
    ],
    animated: true,
  }
}

export const typescriptButtonPadRenderer: ButtonPadRenderer = {
  createState: (commands, nowMs, previous) => {
    let tracks: Track[] | null = null
    let covered = 0
    for (const [commandIndex, command] of commands.entries()) {
      const decoded = decode(command)
      if (decoded === null) return null
      if (decoded.commit !== (commandIndex === commands.length - 1)) return null
      if (decoded.replaceAll !== (commandIndex === 0)) return null
      if (covered & decoded.mask) return null
      covered |= decoded.mask
      if (decoded.replaceAll)
        tracks = Array.from({ length: LED_COUNT }, () => decoded.track)
      if (tracks === null) return null
      for (let index = 0; index < LED_COUNT; index += 1) {
        if (decoded.mask & (1 << index)) tracks[index] = decoded.track
      }
    }
    if (tracks === null || covered !== 0xffff) return null
    const prior = previous as RendererState | null
    return {
      tracks,
      startedAt: tracks.map((track, index) =>
        prior !== null && sameTrack(track, prior.tracks[index])
          ? prior.startedAt[index]
          : nowMs
      ),
    } satisfies RendererState
  },
  render: (stateValue, nowMs) => {
    const state = stateValue as RendererState
    if (!Array.isArray(state?.tracks) || !Array.isArray(state?.startedAt))
      return null
    let animationMask = 0
    const frame = state.tracks.map((track, index) => {
      const rendered = renderTrack(track, index, nowMs - state.startedAt[index])
      if (rendered.animated) animationMask |= 1 << index
      return rendered.rgb
    })
    return { frame, animationMask }
  },
}

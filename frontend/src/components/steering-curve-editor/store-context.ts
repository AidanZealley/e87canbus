import { createContext, useContext } from "react"
import { useStore } from "zustand"

import type {
  createSteeringCurveEditorStore,
  SteeringCurveEditorStore,
} from "./store"

type EditorStore = ReturnType<typeof createSteeringCurveEditorStore>

export const SteeringCurveEditorContext = createContext<EditorStore | null>(
  null
)

export const useSteeringCurveEditorStore = <Selected>(
  selector: (state: SteeringCurveEditorStore) => Selected
) => {
  const store = useContext(SteeringCurveEditorContext)
  if (!store) {
    throw new Error(
      "useSteeringCurveEditorStore must be used within SteeringCurveEditorProvider"
    )
  }
  return useStore(store, selector)
}

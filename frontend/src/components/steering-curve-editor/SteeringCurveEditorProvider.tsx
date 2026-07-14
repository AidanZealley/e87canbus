import { useEffect, useState, type ReactNode } from "react"

import type { ActiveSteeringCurve, StoredSteeringProfile } from "@/api/steering"
import { createSteeringCurveEditorStore } from "./store"
import { SteeringCurveEditorContext } from "./store-context"
import type { SteeringCurveEditorEffects } from "./types"

export const SteeringCurveEditorProvider = ({
  activeCurve,
  profiles,
  profilesError,
  effects,
  children,
}: {
  activeCurve: ActiveSteeringCurve
  profiles: StoredSteeringProfile[]
  profilesError: unknown
  effects: SteeringCurveEditorEffects
  children: ReactNode
}) => {
  const [store] = useState(() =>
    createSteeringCurveEditorStore({
      activeCurve,
      profiles,
      profilesError,
      effects,
    })
  )

  useEffect(
    () => store.getState().syncActiveCurve(activeCurve),
    [activeCurve, store]
  )
  useEffect(
    () => store.getState().syncProfiles(profiles, profilesError),
    [profiles, profilesError, store]
  )
  useEffect(() => store.getState().syncEffects(effects), [effects, store])

  return (
    <SteeringCurveEditorContext.Provider value={store}>
      {children}
    </SteeringCurveEditorContext.Provider>
  )
}

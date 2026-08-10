import type { ApiProblemResponse } from "./http/types.gen"
import { zApiProblemResponse } from "./http/zod.gen"

export const isApiProblemResponse = (
  error: unknown
): error is ApiProblemResponse => zApiProblemResponse.safeParse(error).success

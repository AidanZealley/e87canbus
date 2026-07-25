export const buttonProfileStatusLabel = ({
  synchronized,
  sameProfile,
  sameRevision,
}: {
  synchronized: boolean
  sameProfile: boolean
  sameRevision: boolean
}): string => {
  if (!synchronized) return "Status unavailable"
  if (sameProfile && sameRevision) return "Active"
  if (sameProfile) return "Saved changes not active"
  return "Inactive"
}

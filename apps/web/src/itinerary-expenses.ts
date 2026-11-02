/** Expense records are account data and must not be fetched for guest drafts. */
export function canSyncItineraryExpenses(itineraryId: string | null | undefined,
                                         accessToken: string | null | undefined): boolean {
  return Boolean(itineraryId?.trim() && accessToken?.trim());
}

export function hasAuthenticatedSession(accessToken: string | null | undefined): boolean {
  return Boolean(accessToken?.trim());
}

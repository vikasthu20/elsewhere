/** Verified-trip review domain types and validation. */
export type ReviewDraft = { bookingId:string; rating:number; title?:string; body:string; photos?:string[] };
export function validateReview(review:ReviewDraft) { return Boolean(review.bookingId && Number.isInteger(review.rating) && review.rating>=1 && review.rating<=5 && review.body.trim().length>=10); }

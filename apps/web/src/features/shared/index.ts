/** Shared feature contracts. */
export type ApiState<T> = { data:T|null; loading:boolean; error:string|null };
export const currencyFormatter = new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0});
export const formatINR = (amount:number) => currencyFormatter.format(Number.isFinite(amount)?amount:0);

export type MobileTripStop = { id:string; day:number; title:string; note?:string; completed?:boolean };
export type MobileItinerary = { id?:string; origin:string; destination:string; days:number; travellers:number; stops:MobileTripStop[] };
export function countCompletedStops(stops:MobileTripStop[]) { return stops.filter(stop=>stop.completed).length; }

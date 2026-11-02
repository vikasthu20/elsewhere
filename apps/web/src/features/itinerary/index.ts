/** Itinerary planning feature. */
export { PlannerPage } from '../../pages/PublicPages';
export type ItineraryStop = { id:string; day:number; title:string; description?:string; startTime?:string; durationMinutes?:number; latitude?:number; longitude?:number };
export type ItineraryDraft = { origin:string; destination:string; startDate?:string; endDate?:string; days:number; travellers:number; interests:string[]; stops:ItineraryStop[] };
export function groupStopsByDay(stops:ItineraryStop[]) { return stops.reduce<Record<number,ItineraryStop[]>>((groups, stop) => { (groups[stop.day] ??= []).push(stop); return groups; }, {}); }
export function moveStop(stops:ItineraryStop[], stopId:string, targetDay:number, targetIndex:number) {
  const current=stops.find(s=>s.id===stopId); if(!current) return stops;
  const next=stops.filter(s=>s.id!==stopId); const moved={...current,day:targetDay};
  const dayStops=next.filter(s=>s.day===targetDay); dayStops.splice(Math.max(0,Math.min(targetIndex,dayStops.length)),0,moved);
  return [...next.filter(s=>s.day!==targetDay),...dayStops].sort((a,b)=>a.day-b.day);
}

/** Trip budget calculator. All calculations use integer paise/rupees, not floating point money. */
export { BudgetPage } from '../../pages/PublicPages';
export type BudgetInputs = { days:number; travellers:number; vehiclePerDay:number; foodPerPersonPerDay:number; stayPerRoomPerNight:number; rooms:number; fuel:number; tolls:number; tickets:number; other:number; contingencyPercent:number };
export function calculateTripBudget(v:BudgetInputs) {
  const vehicle=Math.max(0,v.days)*Math.max(0,v.vehiclePerDay);
  const food=Math.max(0,v.days)*Math.max(0,v.travellers)*Math.max(0,v.foodPerPersonPerDay);
  const stay=Math.max(0,v.days-1)*Math.max(0,v.rooms)*Math.max(0,v.stayPerRoomPerNight);
  const subtotal=vehicle+food+stay+Math.max(0,v.fuel)+Math.max(0,v.tolls)+Math.max(0,v.tickets)+Math.max(0,v.other);
  const contingency=Math.round(subtotal*Math.max(0,v.contingencyPercent)/100);
  const total=subtotal+contingency;
  return { vehicle,food,stay,subtotal,contingency,total,perPerson: v.travellers>0?Math.round(total/v.travellers):total };
}

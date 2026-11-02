/** Vehicle marketplace and owner listing feature. */
export { VehiclesPage, VehicleDetailPage, OwnerVehicleCreatePage } from '../../pages/PublicPages';
export { vehicles } from '../../data';
export type VehicleCategory = 'Car' | 'SUV' | 'Van' | 'Bus' | 'Bike' | 'Scooter';
export type VehicleSearch = { city?:string; category?:VehicleCategory; seats?:number; maxDailyPrice?:number };

export type MobileDestination = { id:string; name:string; region:string; category:string; image:string; description:string; rating?:number };
export const destinationCategories = ['All','Nature','Coastal','Heritage','Island','Culture','City'] as const;

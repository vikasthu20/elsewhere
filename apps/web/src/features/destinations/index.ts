/** Destination discovery and detail feature. */
export { DestinationsPage, DestinationDetailPage } from '../../pages/PublicPages';
export { destinations } from '../../data';
export type DestinationCategory = 'Nature' | 'Coastal' | 'Heritage' | 'Island' | 'Culture' | 'City';
export function filterDestinations<T extends {name:string;region:string;category:string}>(items:T[], query:string, category='All') {
  const q=query.trim().toLocaleLowerCase();
  return items.filter(item => (category==='All' || item.category===category) && (!q || `${item.name} ${item.region}`.toLocaleLowerCase().includes(q)));
}

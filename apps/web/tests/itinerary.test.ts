import test from 'node:test';
import assert from 'node:assert/strict';
import { groupStopsByDay, moveStop, type ItineraryStop } from '../src/features/itinerary/index.ts';

test('groupStopsByDay groups stops into day-indexed buckets', () => {
  const stops: ItineraryStop[] = [
    { id: 's1', day: 1, title: 'Arrival & check-in' },
    { id: 's2', day: 1, title: 'Evening beach walk' },
    { id: 's3', day: 2, title: 'Heritage town tour' },
    { id: 's4', day: 3, title: 'Departure' }
  ];

  const grouped = groupStopsByDay(stops);
  assert.strictEqual(Object.keys(grouped).length, 3);
  assert.strictEqual(grouped[1].length, 2);
  assert.strictEqual(grouped[2].length, 1);
  assert.strictEqual(grouped[3].length, 1);
  assert.strictEqual(grouped[1][0].id, 's1');
  assert.strictEqual(grouped[1][1].id, 's2');
});

test('moveStop moves a stop to another day and updates order', () => {
  const stops: ItineraryStop[] = [
    { id: 's1', day: 1, title: 'Stop 1' },
    { id: 's2', day: 1, title: 'Stop 2' },
    { id: 's3', day: 2, title: 'Stop 3' }
  ];

  // Move s2 from day 1 to day 2 at index 0
  const updated = moveStop(stops, 's2', 2, 0);

  const day1 = updated.filter(s => s.day === 1);
  const day2 = updated.filter(s => s.day === 2);

  assert.strictEqual(day1.length, 1);
  assert.strictEqual(day1[0].id, 's1');

  assert.strictEqual(day2.length, 2);
  assert.strictEqual(day2[0].id, 's2');
  assert.strictEqual(day2[1].id, 's3');
});

test('moveStop returns unchanged stops if stopId not found', () => {
  const stops: ItineraryStop[] = [
    { id: 's1', day: 1, title: 'Stop 1' }
  ];

  const result = moveStop(stops, 'non-existent', 2, 0);
  assert.deepStrictEqual(result, stops);
});


import test from 'node:test';
import assert from 'node:assert/strict';
import { destinations, vehicles } from '../src/data.ts';

test('destinations data has required fields and valid ratings', () => {
  assert.ok(destinations.length > 0, 'destinations list should not be empty');

  for (const d of destinations) {
    assert.ok(d.id && d.id.trim().length > 0, `destination ${d.id} has valid id`);
    assert.ok(d.name && d.name.trim().length > 0, `destination ${d.id} has name`);
    assert.ok(d.region && d.region.trim().length > 0, `destination ${d.id} has region`);
    assert.ok(d.category && d.category.trim().length > 0, `destination ${d.id} has category`);
    assert.ok(d.image && d.image.startsWith('http'), `destination ${d.id} has image url`);
    const ratingNum = parseFloat(d.rating);
    assert.ok(ratingNum >= 1 && ratingNum <= 5, `destination ${d.id} rating between 1 and 5`);
  }
});

test('vehicles data has required fields and valid prices', () => {
  assert.ok(vehicles.length > 0, 'vehicles list should not be empty');

  for (const v of vehicles) {
    assert.ok(v.id && v.id.trim().length > 0, `vehicle ${v.id} has valid id`);
    assert.ok(v.name && v.name.trim().length > 0, `vehicle ${v.id} has name`);
    assert.ok(v.type && v.type.trim().length > 0, `vehicle ${v.id} has type`);
    assert.ok(v.city && v.city.trim().length > 0, `vehicle ${v.id} has city`);
    assert.ok(v.seats >= 1, `vehicle ${v.id} has at least 1 seat`);
    assert.ok(v.price > 0, `vehicle ${v.id} has price > 0`);
    assert.ok(Array.isArray(v.features) && v.features.length > 0, `vehicle ${v.id} has features`);
  }
});


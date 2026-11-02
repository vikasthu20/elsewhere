import test from 'node:test';
import assert from 'node:assert/strict';
import { calculateTripBudget } from '../src/features/budget/index.ts';

test('calculateTripBudget computes accurate costs with room nights and contingency', () => {
  const result = calculateTripBudget({
    days: 3,
    travellers: 2,
    vehiclePerDay: 1000,
    foodPerPersonPerDay: 200,
    stayPerRoomPerNight: 1500,
    rooms: 1,
    fuel: 500,
    tolls: 100,
    tickets: 300,
    other: 0,
    contingencyPercent: 10
  });

  // vehicle = 3 * 1000 = 3000
  assert.strictEqual(result.vehicle, 3000);
  // food = 3 * 2 * 200 = 1200
  assert.strictEqual(result.food, 1200);
  // stay = (3 - 1) * 1 * 1500 = 3000
  assert.strictEqual(result.stay, 3000);
  // subtotal = 3000 + 1200 + 3000 + 500 + 100 + 300 + 0 = 8100
  assert.strictEqual(result.subtotal, 8100);
  // contingency = round(8100 * 0.10) = 810
  assert.strictEqual(result.contingency, 810);
  // total = 8910
  assert.strictEqual(result.total, 8910);
  // per person = round(8910 / 2) = 4455
  assert.strictEqual(result.perPerson, 4455);
});

test('calculateTripBudget charges 0 stay for a 1-day trip', () => {
  const result = calculateTripBudget({
    days: 1,
    travellers: 1,
    vehiclePerDay: 1000,
    foodPerPersonPerDay: 100,
    stayPerRoomPerNight: 2000,
    rooms: 1,
    fuel: 0,
    tolls: 0,
    tickets: 0,
    other: 0,
    contingencyPercent: 0
  });

  assert.strictEqual(result.stay, 0);
  assert.strictEqual(result.total, 1100);
  assert.strictEqual(result.perPerson, 1100);
});

test('calculateTripBudget handles negative inputs by clamping to zero', () => {
  const result = calculateTripBudget({
    days: -2,
    travellers: -1,
    vehiclePerDay: -500,
    foodPerPersonPerDay: 0,
    stayPerRoomPerNight: 0,
    rooms: 0,
    fuel: -10,
    tolls: 0,
    tickets: 0,
    other: 0,
    contingencyPercent: -5
  });

  assert.strictEqual(result.total, 0);
  assert.strictEqual(result.perPerson, 0);
});


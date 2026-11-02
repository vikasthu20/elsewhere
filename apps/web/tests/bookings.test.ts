import test from 'node:test';
import assert from 'node:assert/strict';
import { isValidBookingDates } from '../src/features/bookings/index.ts';

test('isValidBookingDates returns true for future valid ranges', () => {
  assert.strictEqual(isValidBookingDates('2026-11-01', '2026-11-05'), true);
});

test('isValidBookingDates returns true for single-day rentals (same start and end)', () => {
  assert.strictEqual(isValidBookingDates('2026-11-01', '2026-11-01'), true);
});

test('isValidBookingDates returns false when end date is before start date', () => {
  assert.strictEqual(isValidBookingDates('2026-11-05', '2026-11-01'), false);
});

test('isValidBookingDates returns false for empty or missing date strings', () => {
  assert.strictEqual(isValidBookingDates('', '2026-11-05'), false);
  assert.strictEqual(isValidBookingDates('2026-11-01', ''), false);
  assert.strictEqual(isValidBookingDates('', ''), false);
});


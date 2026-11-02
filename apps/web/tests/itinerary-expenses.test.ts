import test from 'node:test';
import assert from 'node:assert/strict';
import { canSyncItineraryExpenses, hasAuthenticatedSession } from '../src/itinerary-expenses.js';

test('authenticated itinerary can sync expenses', () => {
  assert.equal(canSyncItineraryExpenses('itinerary-123', 'access-token'), true);
});

test('guest itinerary cannot sync expenses', () => {
  assert.equal(canSyncItineraryExpenses('itinerary-123', null), false);
});

test('missing itinerary cannot sync expenses even with a token', () => {
  assert.equal(canSyncItineraryExpenses(null, 'access-token'), false);
});

test('empty and whitespace credentials cannot sync expenses', () => {
  assert.equal(canSyncItineraryExpenses(' ', 'access-token'), false);
  assert.equal(canSyncItineraryExpenses('itinerary-123', '  '), false);
});

test('saved itinerary GET requires a non-empty authenticated session', () => {
  assert.equal(hasAuthenticatedSession('access-token'), true);
  assert.equal(hasAuthenticatedSession(null), false);
  assert.equal(hasAuthenticatedSession('  '), false);
});

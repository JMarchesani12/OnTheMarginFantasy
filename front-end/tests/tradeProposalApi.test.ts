import assert from 'node:assert/strict';
import test from 'node:test';
import { fixture } from './helpers/leagueContextHarness.ts';
import { TRANSACTION_UNCERTAIN } from '../src/api/safeError.ts';

function proposalApi(response: Response) {
  const api = fixture().load('src/api/transaction.ts', {
    './client': { API_BASE_URL: 'https://api.example.test', apiFetch: async () => response },
  });
  return () => api.tradeRequestProposal(35, 2, 327, 62, 61, [54], [58]);
}

test('trade proposal displays the safe locked-week rejection reason', async () => {
  await assert.rejects(proposalApi(new Response(JSON.stringify({ error: 'Week is locked' }), {
    status: 400,
  })), /week.*locked/i);
});

test('trade proposal uses safe uncertainty feedback for non-JSON server errors', async () => {
  await assert.rejects(proposalApi(new Response('Bad gateway', { status: 502 })),
    (error: Error) => error.message === TRANSACTION_UNCERTAIN);
});

test('trade proposal suppresses arbitrary server diagnostics', async () => {
  await assert.rejects(proposalApi(new Response(JSON.stringify({ error: 'PRIVATE SQL token' }), {
    status: 400,
  })), (error: Error) => error.message === 'Check the entered details and try again.');
});

test('successful trade proposal preserves the response', async () => {
  const result = await proposalApi(new Response(JSON.stringify({ transactionId: 7, status: 'PROPOSED' })))();
  assert.equal(JSON.stringify(result), JSON.stringify({ transactionId: 7, status: 'PROPOSED' }));
});

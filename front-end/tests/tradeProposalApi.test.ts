import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

function proposalApi(response: Response) {
  const source = readFileSync(new URL('../src/api/transaction.ts', import.meta.url), 'utf8');
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const exports: { tradeRequestProposal?: (...args: unknown[]) => Promise<unknown> } = {};
  runInNewContext(output, {
    exports,
    require: (id: string) => {
      assert.equal(id, './client');
      return { API_BASE_URL: 'https://api.example.test', apiFetch: async () => response };
    },
  });
  return () => exports.tradeRequestProposal!(35, 2, 327, 62, 61, [54], [58]);
}

test('trade proposal displays the server rejection reason', async () => {
  await assert.rejects(proposalApi(new Response(JSON.stringify({ error: 'Week is locked' }), {
    status: 400,
  })), /Week is locked/);
});

test('trade proposal uses a trade-specific fallback for non-JSON errors', async () => {
  await assert.rejects(proposalApi(new Response('Bad gateway', { status: 502 })),
    /Failed to submit trade request: 502/);
});

test('successful trade proposal preserves the response', async () => {
  const result = await proposalApi(new Response(JSON.stringify({ transactionId: 7, status: 'PROPOSED' })))();
  assert.equal(JSON.stringify(result), JSON.stringify({ transactionId: 7, status: 'PROPOSED' }));
});

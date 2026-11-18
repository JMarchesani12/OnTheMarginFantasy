import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './helpers/leagueContextHarness.ts';
test('bootstrap API retains explicit credentials/signal/status and displayName-only payload',async()=>{
 const h=fixture(),calls:any[]=[];let status=200;const api=h.load('src/api/user.ts',{'./client':{API_BASE_URL:'https://api.test',apiFetch:async(...args:any[])=>{calls.push(args);return {status,ok:status<400,json:async()=>({id:1})};}}});const signal=new AbortController().signal;
 await api.getUserByUuid('A','token-A',signal);await api.createUser('Name','token-A',signal);assert.equal(calls[0][1].signal,signal);assert.equal(calls[1][1].signal,signal);assert.equal(calls[0][1].headers.Authorization,'Bearer token-A');assert.deepEqual(JSON.parse(calls[1][1].body),{displayName:'Name'});
 status=404;assert.equal(await api.getUserByUuid('A','token-A',signal),null);status=409;await assert.rejects(api.createUser('Name','token-A',signal),(e:any)=>e.status===409);status=403;await assert.rejects(api.getUserByUuid('A','token-A',signal),(e:any)=>e.status===403);
});
test('successful HTTP with an empty profile body is an invalid response, not confirmed absence',async()=>{
 const h=fixture();const api=h.load('src/api/user.ts',{'./client':{API_BASE_URL:'https://api.test',apiFetch:async()=>({status:200,ok:true,json:async()=>null})}});await assert.rejects(api.getUserByUuid('A','token-A'),/response/i);
});

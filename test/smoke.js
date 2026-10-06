// Starts the server over HTTP, connects two clients and relays a signal.
'use strict';
process.env.HTTP = '1';
process.env.PORT = '0';
const assert = require('assert');
const http = require('http');
const { start } = require('../server');

function sse(port, name, onEvent) {
  const req = http.get({ port, path: `/api/events?name=${name}` }, (res) => {
    let buf = '';
    res.on('data', (c) => {
      buf += c;
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, i);
        buf = buf.slice(i + 2);
        const type = /^event: (.*)$/m.exec(block);
        const data = /^data: (.*)$/m.exec(block);
        if (type && data) onEvent(type[1], JSON.parse(data[1]));
      }
    });
  });
  return req;
}

function post(port, body) {
  return new Promise((resolve, reject) => {
    const req = http.request({ port, path: '/api/signal', method: 'POST', headers: { 'Content-Type': 'application/json' } }, (res) => {
      res.resume();
      res.on('end', () => resolve(res.statusCode));
    });
    req.on('error', reject);
    req.end(JSON.stringify(body));
  });
}

const server = start();
server.on('listening', async () => {
  const { port } = server.address();
  const ids = {};
  const got = new Promise((resolve) => {
    sse(port, 'Alice', (t, d) => { if (t === 'hello') ids.alice = d.id; });
    sse(port, 'Bob', (t, d) => {
      if (t === 'hello') ids.bob = d.id;
      if (t === 'signal') resolve(d);
    });
  });
  while (!ids.alice || !ids.bob) await new Promise((r) => setTimeout(r, 20));

  assert.strictEqual(await post(port, { from: ids.alice, to: 'nobody', data: {} }), 404);
  assert.strictEqual(await post(port, { from: 'nobody', to: ids.bob, data: {} }), 401);
  assert.strictEqual(await post(port, { from: ids.alice, to: ids.bob, data: { type: 'call', video: false } }), 200);
  const msg = await got;
  assert.strictEqual(msg.fromName, 'Alice');
  assert.deepStrictEqual(msg.data, { type: 'call', video: false });

  const page = await new Promise((r) => http.get({ port, path: '/' }, (res) => { res.resume(); r(res.statusCode); }));
  assert.strictEqual(page, 200);
  const traversal = await new Promise((r) => http.get({ port, path: '/../server.js' }, (res) => { res.resume(); r(res.statusCode); }));
  assert.notStrictEqual(traversal, 200);

  console.log('smoke test passed');
  process.exit(0);
});
setTimeout(() => { console.error('timeout'); process.exit(1); }, 5000);

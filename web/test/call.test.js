// End-to-end check: two browsers join, one calls the other, the call connects, then hangs up.
// Run with: npm test   (uses Chromium's fake microphone, so no real audio device is needed)
const assert = require('assert');
const { chromium } = require('playwright');
const { createServer } = require('../server');

const PORT = 18443;

(async () => {
  const server = createServer();
  await new Promise((r) => server.listen(PORT, '127.0.0.1', r));
  const browser = await chromium.launch({
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
  });
  try {
    const open = async (name) => {
      const ctx = await browser.newContext({ ignoreHTTPSErrors: true, permissions: ['microphone'] });
      const page = await ctx.newPage();
      page.on('pageerror', (e) => { throw e; });
      await page.goto(`https://localhost:${PORT}/`);
      await page.fill('#name-input', name);
      await page.click('#join-btn');
      await page.waitForSelector('#home-screen:not([hidden])');
      return page;
    };
    const ram = await open('Ram');
    const shyam = await open('Shyam');

    await ram.click('#user-list button');
    await shyam.waitForSelector('#incoming-screen:not([hidden])');
    assert.strictEqual(await shyam.textContent('#incoming-peer'), 'Ram');
    await shyam.click('#accept-btn');

    for (const p of [ram, shyam]) {
      await p.waitForFunction(() => window.kbCall.state === 'connected', null, { timeout: 15000 });
      await p.waitForFunction(() => document.getElementById('call-status').textContent === 'Connected');
    }
    // Remote audio stream must be attached on both sides.
    for (const p of [ram, shyam]) {
      assert.ok(await p.evaluate(() => document.getElementById('remote-audio').srcObject.getAudioTracks().length === 1));
    }

    await ram.click('#hangup-btn');
    for (const p of [ram, shyam]) {
      await p.waitForSelector('#home-screen:not([hidden])');
      await p.waitForFunction(() => window.kbCall.state === 'idle');
    }

    // Declining works too.
    await shyam.click('#user-list button');
    await ram.waitForSelector('#incoming-screen:not([hidden])');
    await ram.click('#decline-btn');
    await shyam.waitForSelector('#home-screen:not([hidden])');
    assert.match(await shyam.textContent('#toast'), /declined/);

    console.log('PASS: call connected both ways, hang-up and decline work');
  } finally {
    await browser.close();
    server.close();
  }
})().catch((e) => {
  console.error('FAIL:', e);
  process.exit(1);
});

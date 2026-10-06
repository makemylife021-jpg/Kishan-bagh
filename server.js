#!/usr/bin/env node
// LAN calling server: serves the web app and relays WebRTC signaling between
// devices on the same Wi-Fi / hotspot. No internet and no npm packages needed.

const http = require('http');
const https = require('https');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const PORT = Number(process.env.PORT) || 8443;
const USE_HTTP = process.env.HTTP === '1';
const PUBLIC_DIR = path.join(__dirname, 'public');
const CERT_DIR = path.join(__dirname, 'certs');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.webmanifest': 'application/manifest+json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};

// id -> { id, name, res (SSE response), lastSeen }
const peers = new Map();

function lanAddresses() {
  const out = [];
  for (const list of Object.values(os.networkInterfaces())) {
    for (const a of list || []) {
      if (a.family === 'IPv4' && !a.internal) out.push(a.address);
    }
  }
  return out;
}

// Browsers only allow microphone/camera on HTTPS (or localhost), so we create a
// self-signed certificate once with openssl and reuse it.
function loadOrCreateCert() {
  const keyPath = path.join(CERT_DIR, 'key.pem');
  const certPath = path.join(CERT_DIR, 'cert.pem');
  if (!fs.existsSync(keyPath) || !fs.existsSync(certPath)) {
    fs.mkdirSync(CERT_DIR, { recursive: true });
    const san = ['DNS:localhost', 'IP:127.0.0.1', ...lanAddresses().map((ip) => `IP:${ip}`)].join(',');
    execFileSync('openssl', [
      'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
      '-keyout', keyPath, '-out', certPath,
      '-days', '3650', '-subj', '/CN=LAN Call',
      '-addext', `subjectAltName=${san}`,
    ], { stdio: 'ignore' });
  }
  return { key: fs.readFileSync(keyPath), cert: fs.readFileSync(certPath) };
}

function sendEvent(peer, type, data) {
  peer.res.write(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`);
}

function broadcastPeers() {
  const list = [...peers.values()].map((p) => ({ id: p.id, name: p.name }));
  for (const p of peers.values()) sendEvent(p, 'peers', list);
}

function readJson(req, limit = 256 * 1024) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (c) => {
      size += c.length;
      if (size > limit) {
        reject(new Error('body too large'));
        req.destroy();
      } else {
        chunks.push(c);
      }
    });
    req.on('end', () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}'));
      } catch (e) {
        reject(e);
      }
    });
    req.on('error', reject);
  });
}

function json(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(body));
}

function serveStatic(req, res, pathname) {
  const rel = pathname === '/' ? '/index.html' : pathname;
  const file = path.normalize(path.join(PUBLIC_DIR, rel));
  if (!file.startsWith(PUBLIC_DIR + path.sep)) {
    res.writeHead(403).end();
    return;
  }
  fs.readFile(file, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain' }).end('Not found');
      return;
    }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(file)] || 'application/octet-stream',
      'Cache-Control': 'no-cache',
    });
    res.end(data);
  });
}

async function handler(req, res) {
  const url = new URL(req.url, 'http://x');
  const { pathname } = url;

  try {
    // Server-Sent Events stream: presence list + incoming signals for this peer.
    if (req.method === 'GET' && pathname === '/api/events') {
      const name = String(url.searchParams.get('name') || '').trim().slice(0, 40) || 'Guest';
      const id = crypto.randomUUID();
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-store',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      });
      const peer = { id, name, res };
      peers.set(id, peer);
      sendEvent(peer, 'hello', { id });
      broadcastPeers();
      const ping = setInterval(() => res.write(': ping\n\n'), 15000);
      req.on('close', () => {
        clearInterval(ping);
        peers.delete(id);
        for (const p of peers.values()) sendEvent(p, 'left', { id });
        broadcastPeers();
      });
      return;
    }

    // Relay an offer/answer/ICE candidate/control message to another peer.
    if (req.method === 'POST' && pathname === '/api/signal') {
      const { from, to, data } = await readJson(req);
      const sender = peers.get(from);
      const target = peers.get(to);
      if (!sender) return json(res, 401, { error: 'unknown sender' });
      if (!target) return json(res, 404, { error: 'peer offline' });
      sendEvent(target, 'signal', { from, fromName: sender.name, data });
      return json(res, 200, { ok: true });
    }

    if (req.method === 'GET' || req.method === 'HEAD') return serveStatic(req, res, pathname);
    res.writeHead(405).end();
  } catch (err) {
    json(res, 400, { error: err.message });
  }
}

function start() {
  let server;
  let scheme = 'https';
  if (USE_HTTP) {
    server = http.createServer(handler);
    scheme = 'http';
  } else {
    try {
      server = https.createServer(loadOrCreateCert(), handler);
    } catch (err) {
      console.warn('Could not create HTTPS certificate (is openssl installed?). Falling back to HTTP.');
      console.warn('Note: on HTTP, browsers block the microphone except on localhost.\n');
      server = http.createServer(handler);
      scheme = 'http';
    }
  }
  server.listen(PORT, '0.0.0.0', () => {
    const { port } = server.address();
    console.log('LAN Call is running — no internet required.\n');
    console.log('Open one of these on every phone/laptop connected to the same Wi-Fi or hotspot:');
    for (const ip of lanAddresses()) console.log(`  ${scheme}://${ip}:${port}`);
    console.log(`  ${scheme}://localhost:${port}  (this computer)`);
    if (scheme === 'https') {
      console.log('\nThe certificate is self-signed: tap "Advanced" → "Proceed" the first time.');
    }
  });
  return server;
}

if (require.main === module) start();

module.exports = { start, handler, peers };

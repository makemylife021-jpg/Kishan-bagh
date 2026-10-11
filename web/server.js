// Offline calling server for a local network (phone hotspot / Wi-Fi router with no internet).
// Serves the web app over HTTPS (browsers only allow microphone access on secure pages)
// and relays WebRTC call setup messages between the people who are online.
const fs = require('fs');
const https = require('https');
const os = require('os');
const path = require('path');
const selfsigned = require('selfsigned');
const { WebSocketServer } = require('ws');

const PORT = Number(process.env.PORT) || 8443;
const PUBLIC_DIR = path.join(__dirname, 'public');
const CERT_DIR = path.join(__dirname, 'cert');

function localAddresses() {
  return Object.values(os.networkInterfaces())
    .flat()
    .filter((a) => a && a.family === 'IPv4' && !a.internal)
    .map((a) => a.address);
}

// Create a self-signed certificate once and reuse it, so phones only accept the warning once.
function loadCertificate() {
  const keyFile = path.join(CERT_DIR, 'key.pem');
  const certFile = path.join(CERT_DIR, 'cert.pem');
  if (fs.existsSync(keyFile) && fs.existsSync(certFile)) {
    return { key: fs.readFileSync(keyFile), cert: fs.readFileSync(certFile) };
  }
  const altNames = [{ type: 2, value: 'localhost' }, { type: 7, ip: '127.0.0.1' }]
    .concat(localAddresses().map((ip) => ({ type: 7, ip })));
  const pems = selfsigned.generate([{ name: 'commonName', value: 'kishan-bagh-call' }], {
    days: 3650,
    keySize: 2048,
    algorithm: 'sha256',
    extensions: [{ name: 'subjectAltName', altNames }],
  });
  fs.mkdirSync(CERT_DIR, { recursive: true });
  fs.writeFileSync(keyFile, pems.private);
  fs.writeFileSync(certFile, pems.cert);
  return { key: pems.private, cert: pems.cert };
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
};

function serveStatic(req, res) {
  const urlPath = decodeURIComponent(new URL(req.url, 'https://x').pathname);
  const file = path.normalize(path.join(PUBLIC_DIR, urlPath === '/' ? 'index.html' : urlPath));
  if (!file.startsWith(PUBLIC_DIR + path.sep)) {
    res.writeHead(403).end();
    return;
  }
  fs.readFile(file, (err, data) => {
    if (err) {
      res.writeHead(404).end('Not found');
      return;
    }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  });
}

function createServer() {
  const server = https.createServer(loadCertificate(), serveStatic);
  const wss = new WebSocketServer({ server, path: '/ws' });
  const users = new Map(); // id -> { ws, name }
  let nextId = 1;

  const send = (ws, msg) => ws.readyState === ws.OPEN && ws.send(JSON.stringify(msg));
  const broadcastUsers = () => {
    const list = [...users].map(([id, u]) => ({ id, name: u.name }));
    for (const u of users.values()) send(u.ws, { type: 'users', users: list });
  };

  wss.on('connection', (ws) => {
    const id = String(nextId++);

    ws.on('message', (raw) => {
      let msg;
      try {
        msg = JSON.parse(raw);
      } catch {
        return;
      }
      if (msg.type === 'join') {
        const name = String(msg.name || '').trim().slice(0, 40) || `User ${id}`;
        users.set(id, { ws, name });
        send(ws, { type: 'welcome', id });
        broadcastUsers();
      } else if (msg.type === 'signal' && users.has(id)) {
        // Call setup (offer / answer / ICE / hang-up) is passed straight to the other person.
        const target = users.get(String(msg.to));
        if (target) send(target.ws, { type: 'signal', from: id, name: users.get(id).name, data: msg.data });
        else send(ws, { type: 'signal', from: String(msg.to), data: { kind: 'unavailable' } });
      }
    });

    ws.on('close', () => {
      if (users.delete(id)) broadcastUsers();
    });
  });

  return server;
}

if (require.main === module) {
  createServer().listen(PORT, '0.0.0.0', () => {
    console.log('Kishan Bagh offline calling server is running.');
    console.log('Open one of these addresses on every phone/laptop on the same Wi-Fi or hotspot:');
    for (const ip of localAddresses()) console.log(`  https://${ip}:${PORT}`);
    console.log(`  https://localhost:${PORT}  (this computer only)`);
    console.log('The browser will warn that the certificate is not trusted: tap "Advanced" -> "Proceed".');
  });
}

module.exports = { createServer };

# Kishan-bagh — LAN Call

Free **voice and video calls with no internet**. Phones and laptops talk to each other
directly over the same **Wi-Fi router or mobile hotspot**. No mobile data, no SIM balance,
no accounts, no app store.

## How it works

```
 Phone A ──┐                         ┌── Phone B
           │   Wi-Fi / hotspot       │
           └──►  server.js  ◄────────┘   (only used to find each other & ring)
 Phone A ◄═══════ audio/video (WebRTC, peer-to-peer) ═══════► Phone B
```

- `server.js` runs on one device on the network (a laptop, or a phone with Termux).
  It serves the app and relays the "ring / answer" messages. It has **zero npm dependencies**.
- Audio and video go **directly between devices** with WebRTC. No STUN/TURN servers are
  configured, so nothing ever leaves your local network.

## Run it

Requires Node.js 18+ (and `openssl`, which is used once to make an HTTPS certificate).

```bash
npm start
```

It prints addresses like:

```
  https://192.168.43.12:8443
```

1. Connect every phone/laptop to the **same Wi-Fi or hotspot** (internet not required —
   a phone hotspot with mobile data turned off works fine).
2. Open the printed `https://…` address in Chrome/Safari on each device.
3. The certificate is self-signed, so tap **Advanced → Proceed** the first time.
4. Enter your name → **Go online**. Everyone on the network shows up in the list.
5. Tap 📞 for a voice call or 🎥 for a video call.

Tip: tap the browser menu → **Add to Home screen** to use it like a normal app.

### Running the server on an Android phone

Install [Termux](https://termux.dev), then:

```bash
pkg install nodejs openssl git
git clone <this repo> && cd Kishan-bagh
npm start
```

Turn on that phone's hotspot, connect the other phones to it, and open the address shown.

### Options

| Env var  | Default | Meaning                                                   |
|----------|---------|-----------------------------------------------------------|
| `PORT`   | `8443`  | Port to listen on                                         |
| `HTTP=1` | off     | Serve plain HTTP (microphone only works on `localhost`)   |

## Features

- Voice and video calls, peer-to-peer on the local network
- Live list of who is online
- Ringtone + vibration for incoming calls, busy / declined / missed-call handling
- Mute, camera on/off, front/back camera switch, call timer
- Light and dark mode, installable as a home-screen app

## Why HTTPS?

Browsers only allow microphone and camera access on secure (HTTPS) pages. The server
creates a self-signed certificate in `certs/` on first start and reuses it.

## Test

```bash
npm test
```

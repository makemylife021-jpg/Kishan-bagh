// LAN Call client: presence + signaling over Server-Sent Events, media over
// WebRTC. No STUN/TURN servers are used, so calls stay on the local network.
'use strict';

const $ = (id) => document.getElementById(id);
const RTC_CONFIG = { iceServers: [] };
const RING_TIMEOUT_MS = 45000;

const state = {
  myId: null,
  myName: '',
  events: null,
  peers: [],
  call: null, // { peerId, peerName, video, outgoing, pc, stream, pendingIce, startedAt, timer, ringTimer }
  incoming: null, // { from, fromName, video }
  facingMode: 'user',
};

// ---------- UI helpers ----------

function show(screenId) {
  for (const s of document.querySelectorAll('.screen')) s.classList.toggle('active', s.id === screenId);
}

let toastTimer;
function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add('hidden'), 3000);
}

function initials(name) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('') || '?';
}

function colorFor(text) {
  let h = 0;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${h} 55% 40%)`;
}

function setAvatar(el, name) {
  el.textContent = initials(name);
  el.style.background = colorFor(name);
}

function renderPeers() {
  const list = $('peer-list');
  list.innerHTML = '';
  const others = state.peers.filter((p) => p.id !== state.myId);
  $('empty').classList.toggle('hidden', others.length > 0);
  for (const p of others) {
    const li = document.createElement('li');
    li.className = 'peer';
    const av = document.createElement('div');
    av.className = 'avatar';
    setAvatar(av, p.name);
    const name = document.createElement('div');
    name.className = 'name';
    name.textContent = p.name;
    const voice = document.createElement('button');
    voice.textContent = '📞';
    voice.title = voice.ariaLabel = `Voice call ${p.name}`;
    voice.onclick = () => startCall(p, false);
    const video = document.createElement('button');
    video.textContent = '🎥';
    video.title = video.ariaLabel = `Video call ${p.name}`;
    video.onclick = () => startCall(p, true);
    li.append(av, name, voice, video);
    list.append(li);
  }
}

function setCallState(text) {
  $('call-state').textContent = text;
}

// ---------- Ringtone (generated, no audio files needed) ----------

let ringCtx, ringInterval;
function startRinging(outgoing) {
  stopRinging();
  try {
    ringCtx = ringCtx || new (window.AudioContext || window.webkitAudioContext)();
    ringCtx.resume();
  } catch {
    return;
  }
  const beep = () => {
    const now = ringCtx.currentTime;
    const freqs = outgoing ? [425] : [880, 660];
    freqs.forEach((f, i) => {
      const o = ringCtx.createOscillator();
      const g = ringCtx.createGain();
      o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, now + i * 0.4);
      g.gain.exponentialRampToValueAtTime(outgoing ? 0.05 : 0.15, now + i * 0.4 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.4 + (outgoing ? 1 : 0.35));
      o.connect(g).connect(ringCtx.destination);
      o.start(now + i * 0.4);
      o.stop(now + i * 0.4 + 1.05);
    });
    if (!outgoing && navigator.vibrate) navigator.vibrate([400, 200, 400]);
  };
  beep();
  ringInterval = setInterval(beep, outgoing ? 3000 : 2000);
}

function stopRinging() {
  clearInterval(ringInterval);
  if (navigator.vibrate) navigator.vibrate(0);
}

// ---------- Signaling ----------

async function signal(to, data) {
  try {
    const res = await fetch('/api/signal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from: state.myId, to, data }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

function connect() {
  const es = new EventSource(`/api/events?name=${encodeURIComponent(state.myName)}`);
  state.events = es;
  es.addEventListener('hello', (e) => {
    state.myId = JSON.parse(e.data).id;
    $('conn-dot').classList.add('on');
    $('conn-text').textContent = 'Online';
  });
  es.addEventListener('peers', (e) => {
    state.peers = JSON.parse(e.data);
    renderPeers();
  });
  es.addEventListener('left', (e) => {
    const { id } = JSON.parse(e.data);
    if (state.call && state.call.peerId === id) endCall('Call ended — they went offline', false);
    if (state.incoming && state.incoming.from === id) dismissIncoming();
  });
  es.addEventListener('signal', (e) => onSignal(JSON.parse(e.data)));
  es.onerror = () => {
    // EventSource reconnects automatically; we get a new id on reconnect.
    $('conn-dot').classList.remove('on');
    $('conn-text').textContent = 'Reconnecting…';
    if (state.call) endCall('Connection to server lost', false);
  };
}

async function onSignal({ from, fromName, data }) {
  const call = state.call;
  switch (data.type) {
    case 'call':
      if (call || state.incoming) {
        signal(from, { type: 'busy' });
        return;
      }
      state.incoming = { from, fromName, video: !!data.video };
      setAvatar($('incoming-avatar'), fromName);
      $('incoming-name').textContent = fromName;
      $('incoming-kind').textContent = data.video ? 'Incoming video call' : 'Incoming voice call';
      $('incoming').classList.remove('hidden');
      startRinging(false);
      if ('Notification' in window && Notification.permission === 'granted' && document.hidden) {
        new Notification(`${fromName} is calling`, { tag: 'lan-call' });
      }
      return;

    case 'cancel':
      if (state.incoming && state.incoming.from === from) {
        dismissIncoming();
        toast(`Missed call from ${fromName}`);
      }
      return;
  }

  if (!call || call.peerId !== from) return;

  switch (data.type) {
    case 'accept':
      // Callee accepted: caller creates the offer.
      stopRinging();
      clearTimeout(call.ringTimer);
      setCallState('Connecting…');
      createPeerConnection();
      try {
        const offer = await call.pc.createOffer();
        await call.pc.setLocalDescription(offer);
        signal(from, { type: 'offer', sdp: call.pc.localDescription });
      } catch (err) {
        endCall('Could not start call', true);
      }
      return;

    case 'offer':
      createPeerConnection();
      await call.pc.setRemoteDescription(data.sdp);
      await flushIce();
      await call.pc.setLocalDescription(await call.pc.createAnswer());
      signal(from, { type: 'answer', sdp: call.pc.localDescription });
      return;

    case 'answer':
      await call.pc.setRemoteDescription(data.sdp);
      await flushIce();
      return;

    case 'ice':
      if (call.pc && call.pc.remoteDescription) {
        try { await call.pc.addIceCandidate(data.candidate); } catch {}
      } else {
        call.pendingIce.push(data.candidate);
      }
      return;

    case 'decline':
      endCall(`${call.peerName} declined`, false);
      return;

    case 'busy':
      endCall(`${call.peerName} is on another call`, false);
      return;

    case 'hangup':
      endCall('Call ended', false);
      return;
  }
}

async function flushIce() {
  const call = state.call;
  if (!call) return;
  for (const c of call.pendingIce.splice(0)) {
    try { await call.pc.addIceCandidate(c); } catch {}
  }
}

// ---------- Media / WebRTC ----------

async function getMedia(video) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error('insecure');
  }
  return navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    video: video ? { facingMode: state.facingMode, width: { ideal: 640 }, height: { ideal: 480 } } : false,
  });
}

function mediaError(err) {
  if (err && err.message === 'insecure') return 'Microphone needs HTTPS — open the https:// address';
  if (err && err.name === 'NotAllowedError') return 'Microphone/camera permission denied';
  if (err && err.name === 'NotFoundError') return 'No microphone/camera found';
  return 'Could not access microphone/camera';
}

function createPeerConnection() {
  const call = state.call;
  const pc = new RTCPeerConnection(RTC_CONFIG);
  call.pc = pc;
  for (const track of call.stream.getTracks()) pc.addTrack(track, call.stream);

  pc.onicecandidate = (e) => {
    if (e.candidate) signal(call.peerId, { type: 'ice', candidate: e.candidate });
  };
  pc.ontrack = (e) => {
    const stream = e.streams[0];
    $('remote-audio').srcObject = stream;
    if (call.video) $('remote-video').srcObject = stream;
  };
  pc.onconnectionstatechange = () => {
    if (state.call !== call) return;
    const s = pc.connectionState;
    if (s === 'connected') onConnected();
    else if (s === 'disconnected') setCallState('Reconnecting…');
    else if (s === 'failed') endCall('Call failed — are you on the same network?', true);
  };
}

function onConnected() {
  const call = state.call;
  $('call').classList.add('connected');
  if (call.startedAt) return;
  call.startedAt = Date.now();
  const tick = () => {
    const s = Math.floor((Date.now() - call.startedAt) / 1000);
    setCallState(`${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`);
  };
  tick();
  call.timer = setInterval(tick, 1000);
}

function openCallScreen(peerName, video) {
  setAvatar($('call-avatar'), peerName);
  $('call-name').textContent = peerName;
  $('call').classList.toggle('video', video);
  $('call').classList.remove('connected');
  $('btn-mute').classList.remove('off');
  $('btn-cam').classList.remove('off');
  $('local-video').srcObject = video ? state.call.stream : null;
  show('call');
}

async function startCall(peer, video) {
  if (state.call) return;
  state.call = { peerId: peer.id, peerName: peer.name, video, outgoing: true, pendingIce: [] };
  try {
    state.call.stream = await getMedia(video);
  } catch (err) {
    state.call = null;
    toast(mediaError(err));
    return;
  }
  openCallScreen(peer.name, video);
  setCallState('Ringing…');
  startRinging(true);
  const ok = await signal(peer.id, { type: 'call', video });
  if (!ok) {
    endCall(`${peer.name} is offline`, false);
    return;
  }
  state.call.ringTimer = setTimeout(() => endCall('No answer', true, 'cancel'), RING_TIMEOUT_MS);
}

async function acceptCall() {
  const inc = state.incoming;
  if (!inc) return;
  dismissIncoming();
  state.call = { peerId: inc.from, peerName: inc.fromName, video: inc.video, outgoing: false, pendingIce: [] };
  try {
    state.call.stream = await getMedia(inc.video);
  } catch (err) {
    signal(inc.from, { type: 'decline' });
    state.call = null;
    toast(mediaError(err));
    return;
  }
  openCallScreen(inc.fromName, inc.video);
  setCallState('Connecting…');
  signal(inc.from, { type: 'accept' });
}

function declineCall() {
  const inc = state.incoming;
  if (!inc) return;
  signal(inc.from, { type: 'decline' });
  dismissIncoming();
}

function dismissIncoming() {
  state.incoming = null;
  stopRinging();
  $('incoming').classList.add('hidden');
}

function endCall(message, notifyPeer, notifyType = 'hangup') {
  const call = state.call;
  if (!call) return;
  state.call = null;
  stopRinging();
  clearTimeout(call.ringTimer);
  clearInterval(call.timer);
  if (notifyPeer) signal(call.peerId, { type: call.startedAt ? 'hangup' : notifyType });
  if (call.pc) call.pc.close();
  if (call.stream) call.stream.getTracks().forEach((t) => t.stop());
  $('remote-audio').srcObject = null;
  $('remote-video').srcObject = null;
  $('local-video').srcObject = null;
  show('contacts');
  if (message) toast(message);
}

function hangUp() {
  const call = state.call;
  if (!call) return;
  // Before the callee answers, a hang-up cancels the ringing on their side.
  const type = call.outgoing && !call.pc ? 'cancel' : 'hangup';
  endCall('Call ended', true, type);
}

function toggleMute() {
  const call = state.call;
  if (!call) return;
  const track = call.stream.getAudioTracks()[0];
  if (!track) return;
  track.enabled = !track.enabled;
  $('btn-mute').classList.toggle('off', !track.enabled);
}

function toggleCamera() {
  const call = state.call;
  if (!call || !call.video) return;
  const track = call.stream.getVideoTracks()[0];
  if (!track) return;
  track.enabled = !track.enabled;
  $('btn-cam').classList.toggle('off', !track.enabled);
}

async function flipCamera() {
  const call = state.call;
  if (!call || !call.video) return;
  state.facingMode = state.facingMode === 'user' ? 'environment' : 'user';
  try {
    const fresh = await navigator.mediaDevices.getUserMedia({ video: { facingMode: state.facingMode } });
    const newTrack = fresh.getVideoTracks()[0];
    const oldTrack = call.stream.getVideoTracks()[0];
    const sender = call.pc && call.pc.getSenders().find((s) => s.track && s.track.kind === 'video');
    if (sender) await sender.replaceTrack(newTrack);
    if (oldTrack) {
      call.stream.removeTrack(oldTrack);
      oldTrack.stop();
    }
    call.stream.addTrack(newTrack);
    $('local-video').srcObject = call.stream;
  } catch {
    toast('Could not switch camera');
  }
}

// ---------- Boot ----------

function goOnline(name) {
  state.myName = name;
  try { localStorage.setItem('lancall-name', name); } catch {}
  $('me-name').textContent = name;
  show('contacts');
  connect();
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission().catch(() => {});
  }
}

$('join-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const name = $('name').value.trim();
  if (name) goOnline(name);
});

$('logout').onclick = () => {
  if (state.events) state.events.close();
  state.events = null;
  state.myId = null;
  state.peers = [];
  $('conn-dot').classList.remove('on');
  $('conn-text').textContent = 'Connecting…';
  show('join');
};

$('btn-accept').onclick = acceptCall;
$('btn-decline').onclick = declineCall;
$('btn-hangup').onclick = hangUp;
$('btn-mute').onclick = toggleMute;
$('btn-cam').onclick = toggleCamera;
$('btn-flip').onclick = flipCamera;

window.addEventListener('beforeunload', () => {
  if (state.call) signal(state.call.peerId, { type: 'hangup' });
});

if (!window.isSecureContext) $('secure-warning').classList.remove('hidden');
try {
  const saved = localStorage.getItem('lancall-name');
  if (saved) $('name').value = saved;
} catch {}

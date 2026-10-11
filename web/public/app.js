// Browser side of Kishan Bagh Call.
// Audio goes directly between the two devices over the local network (WebRTC).
// No STUN/TURN servers are used, so nothing ever needs the internet.
(() => {
  const $ = (id) => document.getElementById(id);
  const RTC_CONFIG = { iceServers: [] };

  let ws = null;
  let myId = null;
  let call = null; // { peerId, peerName, pc, stream, pendingIce, startedAt, outgoing }
  let pendingOffer = null; // offer waiting for the user to answer
  let timerHandle = null;
  let ringer = null;

  // Exposed for automated tests.
  window.kbCall = { get state() { return call ? call.pc.connectionState : 'idle'; } };

  function show(screen) {
    for (const s of ['join-screen', 'home-screen', 'call-screen', 'incoming-screen']) {
      $(s).hidden = s !== screen;
    }
  }

  function toast(text) {
    const t = $('toast');
    t.textContent = text;
    t.hidden = false;
    clearTimeout(toast.handle);
    toast.handle = setTimeout(() => { t.hidden = true; }, 3500);
  }

  function signal(to, data) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'signal', to, data }));
  }

  // ---- Ring tone made with Web Audio, so no sound files are needed ----
  function startRinging() {
    stopRinging();
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const beep = () => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = 440;
        gain.gain.value = 0.15;
        osc.connect(gain).connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.8);
      };
      beep();
      ringer = { ctx, handle: setInterval(beep, 2000) };
    } catch {
      ringer = null;
    }
    if (navigator.vibrate) navigator.vibrate([400, 200, 400]);
  }

  function stopRinging() {
    if (!ringer) return;
    clearInterval(ringer.handle);
    ringer.ctx.close();
    ringer = null;
  }

  // ---- Joining ----
  function join() {
    const name = $('name-input').value.trim();
    if (!name) {
      $('join-error').textContent = 'Please enter your name.';
      $('join-error').hidden = false;
      return;
    }
    try { localStorage.setItem('kb-name', name); } catch {}
    $('join-btn').disabled = true;
    ws = new WebSocket(`wss://${location.host}/ws`);
    ws.onopen = () => ws.send(JSON.stringify({ type: 'join', name }));
    ws.onmessage = (e) => onServerMessage(JSON.parse(e.data));
    ws.onclose = () => {
      endCall(false);
      $('join-btn').disabled = false;
      show('join-screen');
      $('join-error').textContent = 'Lost connection to the calling server. Check that you are on the same Wi-Fi/hotspot, then try again.';
      $('join-error').hidden = false;
    };
    $('my-name').textContent = name;
  }

  function onServerMessage(msg) {
    if (msg.type === 'welcome') {
      myId = msg.id;
      $('join-error').hidden = true;
      show('home-screen');
    } else if (msg.type === 'users') {
      renderUsers(msg.users.filter((u) => u.id !== myId));
      if (call && !msg.users.some((u) => u.id === call.peerId)) {
        toast(`${call.peerName} went offline`);
        endCall(false);
      }
    } else if (msg.type === 'signal') {
      onSignal(msg.from, msg.name, msg.data);
    }
  }

  function renderUsers(users) {
    const list = $('user-list');
    list.replaceChildren();
    for (const u of users) {
      const li = document.createElement('li');
      const name = document.createElement('span');
      name.textContent = u.name;
      const btn = document.createElement('button');
      btn.textContent = 'Call';
      btn.dataset.userId = u.id;
      btn.onclick = () => startCall(u.id, u.name);
      li.append(name, btn);
      list.append(li);
    }
    $('empty-list').hidden = users.length > 0;
  }

  // ---- Calls ----
  async function getMicrophone() {
    return navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      video: false,
    });
  }

  function createPeer(peerId) {
    const pc = new RTCPeerConnection(RTC_CONFIG);
    pc.onicecandidate = (e) => {
      if (e.candidate) signal(peerId, { kind: 'ice', candidate: e.candidate });
    };
    pc.ontrack = (e) => {
      $('remote-audio').srcObject = e.streams[0];
    };
    pc.onconnectionstatechange = () => {
      if (!call || call.pc !== pc) return;
      if (pc.connectionState === 'connected') {
        stopRinging();
        $('call-status').textContent = 'Connected';
        call.startedAt = Date.now();
        timerHandle = setInterval(updateTimer, 1000);
      } else if (pc.connectionState === 'failed') {
        toast('Call could not connect. Are you both on the same Wi-Fi/hotspot?');
        endCall(true);
      }
    };
    return pc;
  }

  function updateTimer() {
    if (!call || !call.startedAt) return;
    const s = Math.floor((Date.now() - call.startedAt) / 1000);
    $('call-timer').textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  }

  function showCallScreen(peerName, status) {
    $('call-peer').textContent = peerName;
    $('call-status').textContent = status;
    $('call-timer').textContent = '00:00';
    $('mute-btn').textContent = 'Mute';
    show('call-screen');
  }

  async function startCall(peerId, peerName) {
    if (call) return;
    let stream;
    try {
      stream = await getMicrophone();
    } catch {
      toast('Microphone permission is needed to make calls.');
      return;
    }
    const pc = createPeer(peerId);
    call = { peerId, peerName, pc, stream, pendingIce: [], startedAt: null, outgoing: true };
    stream.getTracks().forEach((t) => pc.addTrack(t, stream));
    showCallScreen(peerName, 'Ringing…');
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    signal(peerId, { kind: 'offer', sdp: pc.localDescription });
  }

  async function acceptCall() {
    if (!pendingOffer) return;
    const { from, name, sdp, pendingIce } = pendingOffer;
    pendingOffer = null;
    stopRinging();
    let stream;
    try {
      stream = await getMicrophone();
    } catch {
      toast('Microphone permission is needed to answer.');
      signal(from, { kind: 'decline' });
      show('home-screen');
      return;
    }
    const pc = createPeer(from);
    // Candidates that arrived before the user tapped Answer were kept with the offer.
    call = { peerId: from, peerName: name, pc, stream, pendingIce, startedAt: null, outgoing: false };
    stream.getTracks().forEach((t) => pc.addTrack(t, stream));
    showCallScreen(name, 'Connecting…');
    await pc.setRemoteDescription(sdp);
    await flushIce();
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    signal(from, { kind: 'answer', sdp: pc.localDescription });
  }

  function declineCall() {
    if (!pendingOffer) return;
    signal(pendingOffer.from, { kind: 'decline' });
    pendingOffer = null;
    stopRinging();
    show('home-screen');
  }

  async function flushIce() {
    if (!call || !call.pc.remoteDescription) return;
    for (const c of call.pendingIce.splice(0)) {
      try { await call.pc.addIceCandidate(c); } catch {}
    }
  }

  async function onSignal(from, name, data) {
    switch (data.kind) {
      case 'offer':
        if (call || pendingOffer) {
          signal(from, { kind: 'busy' });
          return;
        }
        pendingOffer = { from, name, sdp: data.sdp, pendingIce: [] };
        $('incoming-peer').textContent = name;
        show('incoming-screen');
        startRinging();
        break;
      case 'answer':
        if (call && call.peerId === from) {
          await call.pc.setRemoteDescription(data.sdp);
          await flushIce();
        }
        break;
      case 'ice':
        if (call && call.peerId === from) {
          call.pendingIce.push(data.candidate);
          await flushIce();
        } else if (pendingOffer && pendingOffer.from === from) {
          pendingOffer.pendingIce.push(data.candidate);
        }
        break;
      case 'hangup':
        if (pendingOffer && pendingOffer.from === from) {
          pendingOffer = null;
          stopRinging();
          show('home-screen');
          toast(`Missed call from ${name}`);
        } else if (call && call.peerId === from) {
          toast('Call ended');
          endCall(false);
        }
        break;
      case 'decline':
      case 'busy':
      case 'unavailable':
        if (call && call.peerId === from) {
          toast(data.kind === 'busy' ? `${call.peerName} is on another call` :
            data.kind === 'decline' ? `${call.peerName} declined the call` : 'That person is no longer online');
          endCall(false);
        }
        break;
    }
  }

  function endCall(notifyPeer) {
    stopRinging();
    clearInterval(timerHandle);
    timerHandle = null;
    if (!call) return;
    if (notifyPeer) signal(call.peerId, { kind: 'hangup' });
    call.stream.getTracks().forEach((t) => t.stop());
    call.pc.close();
    $('remote-audio').srcObject = null;
    call = null;
    if (myId) show('home-screen');
  }

  function toggleMute() {
    if (!call) return;
    const track = call.stream.getAudioTracks()[0];
    track.enabled = !track.enabled;
    $('mute-btn').textContent = track.enabled ? 'Mute' : 'Unmute';
  }

  // ---- Wire up the page ----
  try { $('name-input').value = localStorage.getItem('kb-name') || ''; } catch {}
  $('join-btn').onclick = join;
  $('name-input').onkeydown = (e) => { if (e.key === 'Enter') join(); };
  $('hangup-btn').onclick = () => endCall(true);
  $('mute-btn').onclick = toggleMute;
  $('accept-btn').onclick = acceptCall;
  $('decline-btn').onclick = declineCall;

  if (!window.isSecureContext || !navigator.mediaDevices) {
    $('join-error').textContent = 'Open this page using the https:// address shown by the server, otherwise the microphone will not work.';
    $('join-error').hidden = false;
  }
})();

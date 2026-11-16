# WhatsApp Business Cloud in Make: Hinglish explainer reel

Vertical (1080x1920) explainer built from Make's "WhatsApp Business Cloud" help page:
features, requirements, Coexistence mode, the 3 connection steps and webhook setup.

- `script.json`: one row per sentence: `[scene, roman caption, voice text]`. The voice text is
  Devanagari + English (best Hinglish pronunciation); the caption is Roman Hinglish. Same word
  count in both. `*word*` = big green keyword, `^word` = on-screen animation fires there.
- `build.py`: generates `index.html` + `compositions/` from the script.

```bash
python3 build.py                              # preview, estimated timing
python3 build.py --voice voiceover.mp3 --render  # Whisper (Hindi) times captions + animations to the voice
```

Output: `out/make-whatsapp.mp4` (with voice) or `out/make-whatsapp-preview.mp4`.

Credits: Music "Upbeat Corporate" by Soundrider/Dope, CC BY 3.0 (jamendo.com). SFX original.
Voiceover: ElevenLabs voice "Dharmik Hindi" (generated from your ElevenLabs account).

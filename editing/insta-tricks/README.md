# 3 hidden Instagram tricks (lime keyword reel)

Faceless talking-style reel: your voice + word-by-word captions with one huge lime keyword,
a 1-2-3 step tracker and animated phone mockups. Everything is generated from `script.txt`
by `build.py`, so you never hand-edit the timing.

## Make the final video

1. Record `script.txt` on your phone (voice memo is fine). Quiet room, phone 20 cm from your mouth,
   about 2.5 words per second. Leave a short pause between the five paragraphs.
2. Upload the recording, then run:

   ```bash
   cd editing/insta-tricks
   python3 build.py --voice /path/to/recording.m4a --render
   ```

   Whisper times every word to your voice, the captions, tracker and phone animations follow it,
   music drops under your voice, and the video is written to `out/insta-tricks.mp4`.

Without `--voice` you get a silent preview timed to an estimated pace (`out/insta-tricks-preview.mp4`).

## Change the words

Edit `script.txt`: `*word*` = big lime keyword, `^word` = when the phone animation fires.
Re-run `build.py`. Each scene needs its `^` markers (trick1: 2, trick2: 2, trick3: 3, outro: 1).

## Credits (paste in the post description)

Music: "Hip-Hop 1" by Deff Syndicate, CC BY 3.0 (jamendo.com). Sound effects: original.

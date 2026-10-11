// Renders scene.html frame-by-frame and encodes an MP4 with a soft ambient music bed.
// Usage: node render.js [fps] [--preview]   (preview = a few still frames only)
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('child_process');
const path = require('path');

const FPS = Number(process.argv[2]) || 30;
const PREVIEW = process.argv.includes('--preview');
const dir = __dirname;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.goto('file://' + path.join(dir, 'scene.html'));
  await page.evaluate(() => window.ready);
  const total = await page.evaluate(() => window.TOTAL);
  const canvas = await page.$('#c');

  if (PREVIEW) {
    for (const t of (process.env.TS || '3,10,17,30,45,55,70,85,100,108').split(',').map(Number)) {
      await page.evaluate(t => window.renderAt(t), t);
      await canvas.screenshot({ path: path.join(dir, `preview-${t}.png`) });
    }
    await browser.close();
    return;
  }

  const silent = path.join(dir, 'silent.mp4');
  const ff = spawn('ffmpeg', ['-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'medium', silent], { stdio: ['pipe', 'inherit', 'inherit'] });

  const frames = Math.round(total * FPS);
  for (let f = 0; f < frames; f++) {
    await page.evaluate(t => window.renderAt(t), f / FPS);
    const buf = await canvas.screenshot({ type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % 300 === 0) console.log(`frame ${f}/${frames}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();

  // Gentle pad: slowly breathing major chords, low-passed, with fade in/out.
  const d = total.toFixed(2);
  const expr = [
    '0.05*sin(2*PI*261.63*t)*(0.6+0.4*sin(2*PI*0.11*t))',
    '0.04*sin(2*PI*329.63*t)*(0.6+0.4*sin(2*PI*0.07*t+1))',
    '0.04*sin(2*PI*392.00*t)*(0.6+0.4*sin(2*PI*0.09*t+2))',
    '0.03*sin(2*PI*(523.25+ 63.0*gt(mod(t\\,16)\\,8))*t)*(0.5+0.5*sin(2*PI*0.05*t))',
    '0.05*sin(2*PI*130.81*t)',
  ].join('+');
  execFileSync('ffmpeg', ['-y', '-i', silent, '-f', 'lavfi', '-i', `aevalsrc=${expr}:s=44100:d=${d}`,
    '-af', `lowpass=f=1800,aecho=0.8:0.7:60:0.3,afade=t=in:d=2,afade=t=out:st=${(total - 3).toFixed(2)}:d=3`,
    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-shortest', path.join(dir, 'genesis-chapter-1.mp4')], { stdio: 'inherit' });
  require('fs').unlinkSync(silent);
  console.log('done');
})();

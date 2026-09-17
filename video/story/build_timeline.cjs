// Builds timeline.json from the narration clips: each scene starts just before its line and
// holds until the next; the last scene holds a beat after the narration ends.
// usage: node video/story/build_timeline.cjs <voiceDir> <line1file,line2file,...>
const fs = require('fs'), path = require('path'), { execSync } = require('child_process');
const [voiceDir, list] = process.argv.slice(2);
const script = JSON.parse(fs.readFileSync(path.join(__dirname, 'script.json'), 'utf8'));
const files = list.split(',');
const dur = f => parseFloat(execSync(`afinfo "${f}"`).toString().match(/estimated duration: ([\d.]+)/)[1]);
const LEAD = 0.4, GAP = 0.3, TAIL = 1.4, FPS = 30;   // tight pauses: six lines at the narrator's pace land near 35 s
let t = 0; const scenes = [];
script.lines.forEach((line, i) => {
  const file = path.join(voiceDir, files[i]); const d = dur(file);
  const start = i === 0 ? 0 : t;                 // scene begins where the previous ends
  const audioStart = start + LEAD;
  const end = audioStart + d + GAP;
  scenes.push({ id: line.scene, index: i + 1, text: line.text, start: +start.toFixed(3), end: +end.toFixed(3), audio: { file: path.relative(process.cwd(), file), start: +audioStart.toFixed(3), duration: +d.toFixed(3) } });
  t = end;
});
const total = +(t + TAIL).toFixed(3);
scenes[scenes.length - 1].end = total;
const timeline = { fps: FPS, total, frames: Math.ceil(total * FPS), scenes, clips: scenes.map(s => ({ file: s.audio.file, start: s.audio.start })) };
fs.writeFileSync(path.join(__dirname, 'timeline.json'), JSON.stringify(timeline, null, 1));
console.log('total ' + total + 's, ' + timeline.frames + ' frames');
scenes.forEach(s => console.log(`  ${s.index} ${s.id.padEnd(9)} ${s.start.toFixed(2)}–${s.end.toFixed(2)}  voice ${s.audio.duration.toFixed(2)}s`));

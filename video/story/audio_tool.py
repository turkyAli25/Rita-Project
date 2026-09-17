#!/usr/bin/env python3
"""Narration clean-up with numpy only (no ffmpeg/sox on this Mac).

  python3 video/story/audio_tool.py analyze  in.wav                       # levels, noise floor, speech segments, pauses
  python3 video/story/audio_tool.py enhance  in.wav out.wav [--nr 14] [--hp 85] [--presence 2.5] [--rms -19]
  python3 video/story/audio_tool.py split    in.wav outdir b1,b2,...     # cut at boundary times (s) → line1.wav … + .m4a

Decode first with:  afconvert -f WAVE -d LEI16@48000 take.m4a take.wav
"""
import json, os, subprocess, sys, wave
import numpy as np

EPS = 1e-9

def read_wav(path):
    """Own RIFF walk: afconvert writes WAVE_FORMAT_EXTENSIBLE, which the wave module here (3.9) rejects."""
    import struct
    data = open(path, 'rb').read()
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE': raise SystemExit('not a WAV file')
    pos, fmt, pcm = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack('<I', data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b'fmt ': fmt = struct.unpack('<HHIIHH', body[:16])
        elif cid == b'data': pcm = body
        pos += 8 + size + (size & 1)
    _, ch, sr, _, _, bits = fmt
    if bits != 16: raise SystemExit('decode to 16-bit first (afconvert -d LEI16)')
    x = np.frombuffer(pcm[:len(pcm) // 2 * 2], dtype='<i2').astype(np.float32) / 32768.0
    if ch > 1: x = x[:len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
    return x, sr

def write_wav(path, x, sr):
    x = np.clip(x, -1.0, 1.0)
    w = wave.open(path, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((x * 32767.0).astype('<i2').tobytes()); w.close()

def db(v): return 20 * np.log10(np.maximum(v, EPS))

# ---------- framing ----------
def frame_rms(x, sr, win=0.025, hop=0.010):
    n, h = int(sr * win), int(sr * hop)
    if len(x) < n: x = np.pad(x, (0, n - len(x)))
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::h]
    return np.sqrt((frames ** 2).mean(axis=1)), h / sr

def segments(x, sr, gap=0.28, min_len=0.12, margin_db=10.0):
    """Speech regions: frames louder than noise floor + margin (and above -45 dBFS), merged across short gaps."""
    r, hop = frame_rms(x, sr)
    rdb = db(r)
    floor = np.percentile(rdb, 10)
    thr = max(floor + margin_db, -45.0)
    on = rdb > thr
    segs, start = [], None
    for i, v in enumerate(on):
        if v and start is None: start = i
        if not v and start is not None: segs.append([start * hop, i * hop]); start = None
    if start is not None: segs.append([start * hop, len(on) * hop])
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < gap: merged[-1][1] = s[1]
        else: merged.append(s)
    merged = [s for s in merged if s[1] - s[0] >= min_len]
    return merged, floor, thr, rdb, hop

# ---------- STFT ----------
N, HOP = 2048, 512
def stft(x):
    win = np.hanning(N + 1)[:-1]
    pad = np.concatenate([np.zeros(N // 2), x, np.zeros(N)])
    frames = np.lib.stride_tricks.sliding_window_view(pad, N)[::HOP]
    return np.fft.rfft(frames * win, axis=1), win

def istft(S, win, length):
    frames = np.fft.irfft(S, n=N, axis=1) * win
    out = np.zeros(HOP * (len(frames) - 1) + N); wsum = np.zeros_like(out)
    w2 = win ** 2
    for i, f in enumerate(frames):
        out[i * HOP:i * HOP + N] += f; wsum[i * HOP:i * HOP + N] += w2
    out /= np.maximum(wsum, 1e-3)
    return out[N // 2:N // 2 + length]

def enhance(x, sr, nr_db=14.0, hp=85.0, presence_db=2.5, rms_target=-19.0, peak=-1.0):
    S, win = stft(x)
    mag = np.abs(S)
    freqs = np.fft.rfftfreq(N, 1 / sr)
    # --- stationary spectral gate: profile from the quietest 12% of frames, soft mask, floor at -nr_db
    energy = db(mag.mean(axis=1))
    quiet = mag[energy <= np.percentile(energy, 12)]
    n_mean, n_std = quiet.mean(axis=0), quiet.std(axis=0)
    thresh = n_mean + 1.5 * n_std
    mask = (mag > thresh).astype(np.float32)
    k = np.array([0.15, 0.7, 0.15]); kf = np.array([0.2, 0.6, 0.2])
    for _ in range(2):                                  # smooth over time and frequency so the gate does not flutter
        mask = np.apply_along_axis(lambda m: np.convolve(m, k, 'same'), 0, mask)
        mask = np.apply_along_axis(lambda m: np.convolve(m, kf, 'same'), 1, mask)
    mask = np.clip(mask, 0, 1)
    floor = 10 ** (-nr_db / 20)
    gain = floor + (1 - floor) * mask
    # --- tone: high-pass below hp, gentle presence bell at 3 kHz, soft roll-off above 14 kHz
    f = np.maximum(freqs, 1.0)
    hp_gain = 1 / np.sqrt(1 + (hp / f) ** 4)
    bell = 10 ** ((presence_db * np.exp(-(np.log2(f / 3000.0) ** 2) / (2 * 0.6 ** 2))) / 20)
    lp_gain = 1 / np.sqrt(1 + (f / 14000.0) ** 6)
    S = S * gain * (hp_gain * bell * lp_gain)[None, :]
    y = istft(S, win, len(x))
    # --- compressor: 3:1 above -22 dBFS on a 5 ms / 120 ms envelope
    env = np.zeros_like(y); a_att, a_rel = np.exp(-1 / (0.005 * sr)), np.exp(-1 / (0.120 * sr))
    ay = np.abs(y); e = 0.0
    for i in range(len(y)):                            # ~1.9 M samples: fine
        v = ay[i]; e = a_att * e + (1 - a_att) * v if v > e else a_rel * e + (1 - a_rel) * v; env[i] = e
    edb = db(env); thr = -22.0; over = np.maximum(edb - thr, 0)
    y = y * 10 ** (-(over * (1 - 1 / 3.0)) / 20)
    # --- level: speech RMS to target, then a look-ahead peak limiter
    segs, *_ = segments(y, sr)
    act = np.concatenate([y[int(s * sr):int(e * sr)] for s, e in segs]) if segs else y
    y = y * 10 ** ((rms_target - db(np.sqrt((act ** 2).mean()))) / 20)
    lim = 10 ** (peak / 20); la = int(0.005 * sr)
    pk = np.lib.stride_tricks.sliding_window_view(np.pad(np.abs(y), (la, la)), 2 * la + 1).max(axis=1)
    g = np.minimum(1.0, lim / np.maximum(pk, EPS)); rel = np.exp(-1 / (0.050 * sr)); s = 1.0
    for i in range(len(g)):                            # gain may only recover slowly
        s = g[i] if g[i] < s else rel * s + (1 - rel) * g[i]; g[i] = s
    return y * g

def cmd_analyze(path):
    x, sr = read_wav(path)
    segs, floor, thr, rdb, hop = segments(x, sr)
    print(f'{path}: {len(x)/sr:.2f} s, {sr} Hz, peak {db(np.abs(x).max()):.1f} dBFS, noise floor {floor:.1f} dB, speech threshold {thr:.1f} dB')
    for i, (s, e) in enumerate(segs, 1):
        gap = f'  pause before {s - segs[i-2][1]:.2f}s' if i > 1 else ''
        print(f'  seg {i:2d}  {s:6.2f}–{e:6.2f}  ({e - s:5.2f}s){gap}')
    bars = ''.join('▁▂▃▄▅▆▇█'[min(7, max(0, int((v + 60) / 7)))] for v in rdb[::50])   # one glyph per 0.5 s
    print('  envelope: ' + bars)
    print(json.dumps({'segments': segs}))

def cmd_enhance(inp, out, args):
    opts = {'nr': 14.0, 'hp': 85.0, 'presence': 2.5, 'rms': -19.0}
    for i in range(0, len(args), 2): opts[args[i].lstrip('-')] = float(args[i + 1])
    x, sr = read_wav(inp)
    y = enhance(x, sr, opts['nr'], opts['hp'], opts['presence'], opts['rms'])
    write_wav(out, y, sr)
    print(f'wrote {out}: peak {db(np.abs(y).max()):.1f} dBFS, options {opts}')

def cmd_split(inp, outdir, bounds):
    x, sr = read_wav(inp)
    b = [0.0] + [float(v) for v in bounds.split(',')] + [len(x) / sr]
    os.makedirs(outdir, exist_ok=True)
    segs, *_ = segments(x, sr)
    fade = int(0.012 * sr)
    for i in range(len(b) - 1):
        s, e = b[i], b[i + 1]
        inside = [g for g in segs if g[1] > s and g[0] < e]              # trim to the speech inside the cut, ±80 ms
        if inside: s, e = max(s, inside[0][0] - 0.08), min(e, inside[-1][1] + 0.08)
        clip = x[int(s * sr):int(e * sr)].copy()
        clip[:fade] *= np.linspace(0, 1, fade); clip[-fade:] *= np.linspace(1, 0, fade)
        wav = os.path.join(outdir, f'line{i + 1}.wav'); m4a = wav[:-4] + '.m4a'
        write_wav(wav, clip, sr)
        subprocess.run(['afconvert', '-f', 'm4af', '-d', 'aac', '-b', '192000', wav, m4a], check=True)
        print(f'line{i + 1}: {s:.2f}–{e:.2f}  {len(clip)/sr:.2f}s  → {m4a}')

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: raise SystemExit(__doc__)
    if a[0] == 'analyze': cmd_analyze(a[1])
    elif a[0] == 'enhance': cmd_enhance(a[1], a[2], a[3:])
    elif a[0] == 'split': cmd_split(a[1], a[2], a[3])
    else: raise SystemExit(__doc__)

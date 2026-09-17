#!/bin/zsh
# Rebuilds the explainer from six narration files (one per line of script.json), in order.
# usage:  video/story/finalize.sh <line1> <line2> <line3> <line4> <line5> <line6> [output.mp4]
#   e.g.  video/story/finalize.sh video/story/voice/xavier-line{1,2,3,4,5,6}.mp3 "video/outputs/Riati-explainer-35s-Arabic.mp4"
set -e
cd -- "${0:A:h}/../.."
[ $# -ge 6 ] || { echo "need six narration files"; exit 2 }
OUT="${7:-video/outputs/Riati-explainer-Arabic.mp4}"
DIR=$(dirname "$1"); LIST=""
for f in "$1" "$2" "$3" "$4" "$5" "$6"; do [ -s "$f" ] || { echo "missing $f"; exit 1 }; LIST="$LIST${LIST:+,}$(basename "$f")"; done
curl -s -o /dev/null --max-time 3 http://localhost:8735/demo.html || { (nohup python3 -m http.server 8735 > /tmp/riati_static.log 2>&1 &); sleep 1.5 }
[ -x video/story/encode ] || swiftc -swift-version 5 -O video/story/encode.swift -o video/story/encode
[ -x video/story/mux ]    || swiftc -swift-version 5 -O video/story/mux.swift    -o video/story/mux
echo "--- timeline ---";  node video/story/build_timeline.cjs "$DIR" "$LIST"
echo "--- frames ---";    node video/story/render.cjs | tail -n 1
FR=$(python3 -c "import json;print(json.load(open('video/story/timeline.json'))['frames'])")
echo "--- encode ---";    ./video/story/encode video/story/frames "$FR" 30 1920 1080 video/story/silent.mp4 | tail -n 1
echo "--- mux ---";       ./video/story/mux video/story/silent.mp4 video/story/timeline.json "$OUT" | tail -n 1
ls -lh "$OUT"

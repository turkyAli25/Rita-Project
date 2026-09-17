// Silent video + narration clips placed on a timeline → final MP4 (H.264 + AAC).
// usage: mux <silent.mp4> <timeline.json> <out.mp4>
// timeline.json: {"clips":[{"file":"video/story/voice/line1.mp3","start":0.6}, ...]}
import Foundation
import AVFoundation

struct Clip: Decodable { let file: String; let start: Double }
struct Timeline: Decodable { let clips: [Clip] }

let a = CommandLine.arguments
guard a.count == 4 else { print("usage: mux <silent.mp4> <timeline.json> <out.mp4>"); exit(2) }
let tl = try JSONDecoder().decode(Timeline.self, from: Data(contentsOf: URL(fileURLWithPath: a[2])))
let video = AVURLAsset(url: URL(fileURLWithPath: a[1]))
let comp = AVMutableComposition()
let vTrack = comp.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid)!
try vTrack.insertTimeRange(CMTimeRange(start: .zero, duration: video.duration), of: video.tracks(withMediaType: .video)[0], at: .zero)
let aTrack = comp.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)!
for c in tl.clips {
  let clip = AVURLAsset(url: URL(fileURLWithPath: c.file))
  guard let t = clip.tracks(withMediaType: .audio).first else { print("no audio track in \(c.file)"); exit(1) }
  try aTrack.insertTimeRange(CMTimeRange(start: .zero, duration: clip.duration), of: t, at: CMTime(seconds: c.start, preferredTimescale: 600))
  print(String(format: "clip %@ at %.2fs (%.2fs)", (c.file as NSString).lastPathComponent, c.start, CMTimeGetSeconds(clip.duration)))
}
let out = URL(fileURLWithPath: a[3]); try? FileManager.default.removeItem(at: out)
guard let ex = AVAssetExportSession(asset: comp, presetName: AVAssetExportPresetHighestQuality) else { print("no export session"); exit(1) }
ex.outputURL = out; ex.outputFileType = .mp4; ex.shouldOptimizeForNetworkUse = true
let sem = DispatchSemaphore(value: 0); ex.exportAsynchronously { sem.signal() }; sem.wait()
if ex.status != .completed { print("export failed: \(ex.error?.localizedDescription ?? "unknown")"); exit(1) }
let r = AVURLAsset(url: out)
print(String(format: "final: %.2fs  video tracks %d  audio tracks %d", CMTimeGetSeconds(r.duration), r.tracks(withMediaType: .video).count, r.tracks(withMediaType: .audio).count))

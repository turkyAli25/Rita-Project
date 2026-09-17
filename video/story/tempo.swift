// Pitch-preserving tempo change through AVAudioUnitTimePitch, rendered offline.
// usage: tempo <in.wav> <out.wav> <rate> [cents]   (rate 1.08 = 8 % faster; cents shifts pitch, 100 = one semitone, negative = deeper)
import Foundation
import AVFoundation

let a = CommandLine.arguments
guard a.count >= 4, let rate = Float(a[3]) else { print("usage: tempo <in.wav> <out.wav> <rate> [cents]"); exit(2) }
let cents = a.count > 4 ? (Float(a[4]) ?? 0) : 0
let file = try AVAudioFile(forReading: URL(fileURLWithPath: a[1]))
let fmt = file.processingFormat
let engine = AVAudioEngine(), player = AVAudioPlayerNode(), tp = AVAudioUnitTimePitch()
tp.rate = rate; tp.pitch = cents; tp.overlap = 8
engine.attach(player); engine.attach(tp)
engine.connect(player, to: tp, format: fmt)
engine.connect(tp, to: engine.mainMixerNode, format: fmt)
try engine.enableManualRenderingMode(.offline, format: fmt, maximumFrameCount: 4096)
try engine.start()
player.scheduleFile(file, at: nil)
player.play()
func render() throws {   // the writer must be released before exit, or the WAV header keeps a zero length
  let out = try AVAudioFile(forWriting: URL(fileURLWithPath: a[2]),
                            settings: [AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: fmt.sampleRate,
                                       AVNumberOfChannelsKey: fmt.channelCount, AVLinearPCMBitDepthKey: 16,
                                       AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false],
                            commonFormat: fmt.commonFormat, interleaved: fmt.isInterleaved)
  let buf = AVAudioPCMBuffer(pcmFormat: engine.manualRenderingFormat, frameCapacity: engine.manualRenderingMaximumFrameCount)!
  let total = AVAudioFramePosition(Double(file.length) / Double(rate)) + AVAudioFramePosition(fmt.sampleRate * 0.15)   // small tail for the unit's latency
  while engine.manualRenderingSampleTime < total {
    let n = min(buf.frameCapacity, AVAudioFrameCount(total - engine.manualRenderingSampleTime))
    let st = try engine.renderOffline(n, to: buf)
    if st == .success { try out.write(from: buf) } else if st == .insufficientDataFromInputNode { continue } else { break }
  }
  print(String(format: "tempo x%.2f, pitch %+.0f cents: %.2fs → %.2fs", rate, cents, Double(file.length) / fmt.sampleRate, Double(engine.manualRenderingSampleTime) / fmt.sampleRate))
}
try render()
engine.stop()

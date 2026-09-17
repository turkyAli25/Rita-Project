// Frames (JPEG, numbered 0000.jpg…) → silent H.264 MP4.
// usage: encode <framesDir> <count> <fps> <width> <height> <out.mp4>
import Foundation
import AVFoundation
import CoreGraphics
import ImageIO

let a = CommandLine.arguments
guard a.count == 7 else { print("usage: encode <framesDir> <count> <fps> <width> <height> <out.mp4>"); exit(2) }
let dir = URL(fileURLWithPath: a[1]); let count = Int(a[2])!; let fps = Int32(a[3])!; let W = Int(a[4])!; let H = Int(a[5])!
let out = URL(fileURLWithPath: a[6])
try? FileManager.default.removeItem(at: out)
let writer = try AVAssetWriter(outputURL: out, fileType: .mp4)
let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
  AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: W, AVVideoHeightKey: H,
  AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 14_000_000, AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel, AVVideoMaxKeyFrameIntervalKey: Int(fps)]])
input.expectsMediaDataInRealTime = false
let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
  kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB, kCVPixelBufferWidthKey as String: W, kCVPixelBufferHeightKey as String: H,
  kCVPixelBufferCGImageCompatibilityKey as String: true, kCVPixelBufferCGBitmapContextCompatibilityKey as String: true])
writer.add(input); writer.shouldOptimizeForNetworkUse = true
writer.startWriting(); writer.startSession(atSourceTime: .zero)
for i in 0..<count {
  while !input.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.004) }
  try autoreleasepool {
    let path = dir.appendingPathComponent(String(format: "%04d.jpg", i))
    guard let src = CGImageSourceCreateWithURL(path as CFURL, nil), let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { throw NSError(domain: "ImageRead", code: i) }
    var opt: CVPixelBuffer?; CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &opt)
    let buf = opt!; CVPixelBufferLockBaseAddress(buf, [])
    let ctx = CGContext(data: CVPixelBufferGetBaseAddress(buf), width: W, height: H, bitsPerComponent: 8, bytesPerRow: CVPixelBufferGetBytesPerRow(buf), space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue)!
    ctx.draw(img, in: CGRect(x: 0, y: 0, width: W, height: H)); CVPixelBufferUnlockBaseAddress(buf, [])
    if !adaptor.append(buf, withPresentationTime: CMTime(value: Int64(i), timescale: fps)) { throw writer.error ?? NSError(domain: "Encode", code: i) }
  }
  if i % 150 == 0 { print("encoded \(i)/\(count)") }
}
writer.endSession(atSourceTime: CMTime(value: Int64(count), timescale: fps)); input.markAsFinished()
let sem = DispatchSemaphore(value: 0); writer.finishWriting { sem.signal() }; sem.wait()
if let e = writer.error { print("error: \(e)"); exit(1) }
let asset = AVURLAsset(url: out)
print("silent video: \(CMTimeGetSeconds(asset.duration))s  \(W)x\(H)@\(fps)")

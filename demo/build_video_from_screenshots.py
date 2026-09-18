"""
Assemble the screenshots captured by selenium_capture.py into an actual
video file - a real, automated artifact, but a slideshow of real frames
rather than a continuous screen recording (use that if you have a live X
display + ffmpeg available; see the note at the top of selenium_capture.py).

Requires ffmpeg on PATH. Usage:
    python3 build_video_from_screenshots.py [screenshots_dir] [output.mp4] [seconds_per_frame]
"""
import subprocess
import sys
from pathlib import Path


def main():
    shots_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "./selenium_screenshots")
    out_path = sys.argv[2] if len(sys.argv) > 2 else "./selenium_capture_video.mp4"
    seconds_per_frame = sys.argv[3] if len(sys.argv) > 3 else "3"

    frames = sorted(shots_dir.glob("*.png"))
    if not frames:
        print(f"No .png files found in {shots_dir}")
        sys.exit(1)

    list_path = shots_dir / "frames.txt"
    with open(list_path, "w") as f:
        for frame in frames:
            f.write(f"file '{frame.resolve()}'\n")
            f.write(f"duration {seconds_per_frame}\n")
        # concat demuxer requires the last file repeated with no duration
        f.write(f"file '{frames[-1].resolve()}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-vf", "scale=1440:900:force_original_aspect_ratio=decrease,"
               "pad=1440:900:(ow-iw)/2:(oh-ih)/2,fps=10",
        "-pix_fmt", "yuv420p", out_path,
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"\nDone: {out_path} ({len(frames)} frames, {seconds_per_frame}s each)")


if __name__ == "__main__":
    main()

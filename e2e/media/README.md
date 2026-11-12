# Test media

- `lesson.mp4`: 8 seconds of a test pattern, 320×180, VP9 in MP4 (40 KB). VP9, not H.264, because
  Playwright's Chromium has no H.264 decoder. Made with ffmpeg:
  `ffmpeg -f lavfi -i "testsrc2=size=320x180:rate=10:duration=8" -c:v libvpx-vp9 -b:v 40k -pix_fmt yuv420p -movflags +faststart lesson.mp4`
- `lesson.vtt`: its captions.

`tests/fixtures.ts` uploads both through the staff API for every test that needs a video.

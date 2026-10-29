"""Video processor service using ffmpeg for TikTok & Shorts rendering."""
import os
import math
import shutil
import subprocess
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


@dataclass
class VideoProcessConfig:
    output_folder: str = "./output"
    target_duration: float = 61.2  # 1 phút 1.2 giây (đủ chuẩn quỹ sáng tạo TikTok Creator Rewards)
    watermark_path: Optional[str] = None


class VideoProcessor:
    def __init__(self, config: Optional[VideoProcessConfig] = None, ffmpeg_path: str = "ffmpeg"):
        self.config = config or VideoProcessConfig()
        self.ffmpeg_path = self._resolve_ffmpeg(ffmpeg_path)
        self.ffprobe_path = self._resolve_ffprobe()
        os.makedirs(self.config.output_folder, exist_ok=True)

    def _resolve_ffmpeg(self, path: str) -> str:
        if path and os.path.exists(path):
            return path
        found = shutil.which(path)
        if found:
            return found
        candidates = [
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
            os.path.join(os.path.dirname(__file__), "..", "..", "ffmpeg.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return "ffmpeg"

    def _resolve_ffprobe(self) -> str:
        found = shutil.which("ffprobe")
        if found:
            return found
        candidates = [
            r"C:\ProgramData\chocolatey\bin\ffprobe.exe",
            os.path.join(os.path.dirname(self.ffmpeg_path), "ffprobe.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return "ffprobe"

    def _build_video_filename(self, video_id: str, video_title: str, ext: str = ".mp4") -> str:
        safe_title = "".join(c for c in video_title if c.isalnum() or c in (" ", "_", "-")).rstrip()
        safe_title = safe_title[:50].strip() or "video"
        return f"{safe_title}_{video_id}{ext}"

    def _build_ffmpeg_http_opts(self) -> List[str]:
        return [
            "-headers",
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
            "X-YouTube-Client-Name: ANDROID\r\n"
            "X-YouTube-Client-Version: 20.10.38\r\n"
        ]

    def _get_startupinfo(self):
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return si
        return None

    def _detect_hardware_encoder(self):
        """Tự động phát hiện GPU encoder (MediaFoundation / NVENC / QSV / AMF) để tăng tốc render 61s."""
        if hasattr(self, "_cached_hw_encoder") and self._cached_hw_encoder:
            return self._cached_hw_encoder

        candidates = [
            ("h264_mf", ["-c:v", "h264_mf"]),
            ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p1"]),
            ("h264_qsv", ["-c:v", "h264_qsv"]),
            ("h264_amf", ["-c:v", "h264_amf", "-quality", "speed"]),
        ]
        si = self._get_startupinfo()
        for enc_name, enc_args in candidates:
            test_cmd = [self.ffmpeg_path, "-f", "lavfi", "-i", "nullsrc=s=1280x720:d=0.1", "-c:v", enc_name, "-f", "null", "-"]
            try:
                res = subprocess.run(test_cmd, startupinfo=si, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                if res.returncode == 0:
                    logger.info(f"🚀 Kích hoạt GPU Hardware Acceleration thành công: {enc_name}")
                    self._cached_hw_encoder = (enc_name, enc_args)
                    return self._cached_hw_encoder
            except Exception:
                pass

        # Dự phòng CPU ultrafast với đa luồng tối đa
        self._cached_hw_encoder = ("libx264", ["-c:v", "libx264", "-preset", "ultrafast", "-threads", "0"])
        return self._cached_hw_encoder

    def _run_ffmpeg(self, cmd: List[str]) -> bool:
        try:
            res = subprocess.run(
                cmd,
                startupinfo=self._get_startupinfo(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode(errors="ignore") if e.stderr else str(e)
            logger.error(f"FFmpeg process error: {err_msg}")
            return False
        except Exception as e:
            logger.error(f"FFmpeg error: {e}")
            return False

    def get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds using ffprobe, fallback to ffmpeg."""
        if not os.path.exists(video_path):
            return 0.0

        # Try ffprobe
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]
            res = subprocess.run(
                cmd,
                startupinfo=self._get_startupinfo(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=True
            )
            out_str = res.stdout.decode().strip()
            if out_str:
                return float(out_str)
        except Exception as e:
            logger.debug(f"ffprobe duration check failed: {e}")

        # Fallback to ffmpeg -i parsing
        try:
            cmd = [self.ffmpeg_path, "-i", video_path]
            res = subprocess.run(
                cmd,
                startupinfo=self._get_startupinfo(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10
            )
            err_str = res.stderr.decode(errors="ignore")
            # Look for Duration: 00:00:45.32
            import re
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", err_str)
            if m:
                h, mins, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                return h * 3600 + mins * 60 + s
        except Exception as e:
            logger.error(f"FFmpeg duration check error: {e}")

        return 0.0

    def edit_video_for_tiktok(
        self,
        input_path: str,
        output_path: str,
        mode: str = "extend_61s",
        quality: str = "720",
        target_duration: float = 61.2,
        watermark_path: Optional[str] = None
    ) -> bool:
        """
        Process video according to selected mode:
        1. 'direct' (Tải up luôn):
           - Quick remux or ultrafast 9:16 vertical crop/scale without duration extension.
        2. 'extend_61s' (Edit đủ 1 phút 1 giây):
           - Checks duration using ffprobe.
           - If < 61s, loops video and audio using -stream_loop to reach >= 61.2s (1m01s)
             to qualify for TikTok Creator Rewards.
           - Formats to 9:16 vertical resolution (720x1280 or 1080x1920).
        """
        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return False

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        width = 1080 if quality == "1080" else 720
        height = 1920 if quality == "1080" else 1280

        # Mode 1: Tải up luôn (Direct) - Tải xong up ngay lập tức, không re-encode gây chậm trễ
        if mode == "direct":
            if not watermark_path or not os.path.exists(watermark_path):
                logger.info(f"Chế độ 'Tải up luôn': Tối ưu tốc độ tối đa, bỏ qua render FFmpeg để upload ngay (0s)!")
                try:
                    shutil.copy2(input_path, output_path)
                    return True
                except Exception as e:
                    logger.error(f"Lỗi sao chép video tải up luôn: {e}")
                    return False
            else:
                logger.info(f"Direct mode có watermark: Render nhanh với preset ultrafast...")
                return self.render_for_tiktok(
                    input_path=input_path,
                    output_path=output_path,
                    width=width,
                    height=height,
                    watermark_path=watermark_path,
                    use_fast_preset=True
                )

        # Mode 2: Edit đủ 1 phút 1 giây (extend_61s)
        dur = self.get_video_duration(input_path)
        logger.info(f"Input video duration: {dur:.2f}s (Target: {target_duration:.2f}s, Quality: {quality}p)")

        # Nếu video đã sẵn >= 61s và không có watermark thì bỏ qua render luôn để up ngay!
        if dur >= target_duration and (not watermark_path or not os.path.exists(watermark_path)):
            logger.info(f"Video đã đủ {dur:.2f}s (>= {target_duration:.1f}s): Đã đủ điều kiện TikTok, không cần lặp lại (0s render)!")
            try:
                shutil.copy2(input_path, output_path)
                return True
            except Exception as e:
                logger.error(f"Lỗi sao chép video: {e}")
                return False

        # Prepare 9:16 vertical filter
        vf_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
        inputs = []

        if dur > 0 and dur < target_duration:
            # Need looping
            loops = max(1, int(math.ceil(target_duration / dur)))
            logger.info(f"Video is {dur:.2f}s (< 61s). Looping {loops} times to reach {target_duration:.2f}s.")
            inputs = ["-stream_loop", str(loops), "-i", input_path]
            time_limit = ["-t", str(target_duration)]
        else:
            inputs = ["-i", input_path]
            time_limit = []

        if watermark_path and os.path.exists(watermark_path):
            inputs.extend(["-i", watermark_path])
            filter_complex = (
                f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v0];"
                f"[1:v]scale={int(width*0.22)}:-1[wm];"
                f"[v0][wm]overlay=W-w-20:25[outv]"
            )
            v_args = ["-filter_complex", filter_complex, "-map", "[outv]", "-map", "0:a?"]
        else:
            v_args = ["-vf", vf_filter]

        hw_name, hw_v_args = self._detect_hardware_encoder()
        codec_args = hw_v_args + [
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k"
        ]

        cmd = [self.ffmpeg_path, "-y"] + inputs + time_limit + v_args + codec_args + [output_path]
        logger.info(f"Running FFmpeg 61s extend ({hw_name}): {' '.join(cmd)}")
        return self._run_ffmpeg(cmd)

    def render_for_tiktok(
        self,
        input_path: str,
        output_path: str,
        width: int = 720,
        height: int = 1280,
        watermark_path: Optional[str] = None,
        use_vp9: bool = False,
        use_fast_preset: bool = False
    ) -> bool:
        """
        Render video into vertical 9:16 aspect ratio suitable for TikTok & Shorts.
        """
        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return False

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        vf_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
        inputs = ["-i", input_path]

        if watermark_path and os.path.exists(watermark_path):
            inputs.extend(["-i", watermark_path])
            filter_complex = (
                f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1[v0];"
                f"[1:v]scale={int(width*0.22)}:-1[wm];"
                f"[v0][wm]overlay=W-w-20:25[outv]"
            )
            v_args = ["-filter_complex", filter_complex, "-map", "[outv]", "-map", "0:a?"]
        else:
            v_args = ["-vf", vf_filter]

        preset = "ultrafast" if use_fast_preset else "fast"
        if use_vp9:
            codec_args = ["-c:v", "libvpx-vp9", "-b:v", "1800k", "-c:a", "libopus"]
        else:
            codec_args = ["-c:v", "libx264", "-preset", preset, "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k"]

        cmd = [self.ffmpeg_path, "-y"] + inputs + v_args + codec_args + [output_path]
        return self._run_ffmpeg(cmd)

    def process_video_360vp9(self, input_path: str, output_path: str) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cmd = [self.ffmpeg_path, "-y", "-i", input_path, "-c:v", "libvpx-vp9", "-s", "360x640", output_path]
        return self._run_ffmpeg(cmd)

    def process_720vp9(self, input_path: str, output_path: str) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cmd = [self.ffmpeg_path, "-y", "-i", input_path, "-c:v", "libvpx-vp9", "-s", "720x1280", output_path]
        return self._run_ffmpeg(cmd)

    def process_1080dl(self, input_path: str, output_path: str) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cmd = [self.ffmpeg_path, "-y", "-i", input_path, "-c:v", "copy", output_path]
        return self._run_ffmpeg(cmd)

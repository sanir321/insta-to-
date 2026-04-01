import os
import ffmpeg
from core.status import status_manager

class VideoProcessor:
    def process_video(self, input_path):
        status_manager.update(action="Processing", progress=50, step="Scaling & Re-encoding (FFmpeg)")
        output_path = input_path.replace(".mp4", "_processed.mp4")
        
        try:
            (
                ffmpeg
                .input(input_path)
                .filter('scale', 1080, 1920)
                .output(output_path, vcodec='libx264', crf=23, preset='fast', acodec='aac', pix_fmt='yuv420p')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            status_manager.log(f"🎬 Processed: {os.path.basename(output_path)}")
            return output_path
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            status_manager.log(f"❌ FFmpeg error: {error_msg}")
            return input_path
        except Exception as e:
            status_manager.log(f"❌ Processing failed: {e}")
            return input_path

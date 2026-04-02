import os
import ffmpeg
from core.status import status_manager

class VideoProcessor:
    def process_video(self, input_path, channel_number=1):
        """
        Process and re-encode a video for the given channel.

        Channel 1 uses H.264 (libx264, CRF 23) and Channel 2 uses H.265
        (libx265, CRF 22).  Different codecs produce different file
        signatures so YouTube won't flag the uploads as duplicates.
        Both channels output at 1080x1920 (Shorts portrait format).
        """
        channel_number = channel_number if channel_number in (1, 2) else 1

        if channel_number == 2:
            codec   = 'libx265'
            crf     = 22
            suffix  = '_ch2_processed.mp4'
            codec_label = 'H.265'
        else:
            codec   = 'libx264'
            crf     = 23
            suffix  = '_ch1_processed.mp4'
            codec_label = 'H.264'

        status_manager.update(
            action="Processing",
            progress=50,
            step=f"Scaling & Re-encoding ({codec_label}) for Channel {channel_number}"
        )
        output_path = input_path.replace(".mp4", suffix)

        try:
            (
                ffmpeg
                .input(input_path)
                .filter('scale', 1080, 1920)
                .output(
                    output_path,
                    vcodec=codec,
                    crf=crf,
                    preset='fast',
                    acodec='aac',
                    pix_fmt='yuv420p'
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            status_manager.log(
                f"🎬 Processed (Channel {channel_number}, {codec_label}): "
                f"{os.path.basename(output_path)}"
            )
            return output_path
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            status_manager.log(f"❌ FFmpeg error: {error_msg}")
            return input_path
        except Exception as e:
            status_manager.log(f"❌ Processing failed: {e}")
            return input_path

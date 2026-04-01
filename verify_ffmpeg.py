import ffmpeg
import os
import sys

def verify_ffmpeg():
    print("[INFO] Checking FFmpeg environment...")
    
    # 1. Try to get version
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("[SUCCESS] FFmpeg binary found:")
            print(result.stdout.split('\n')[0])
        else:
            print("[FAILURE] FFmpeg binary returned non-zero exit code.")
            return False
    except Exception as e:
        print(f"[FAILURE] FFmpeg binary not found in PATH: {e}")
        return False

    # 2. Try to create a dummy video and process it
    print("\n[TESTING] Testing video encoding (libx264 + aac)...")
    test_input = "test_pattern.mp4"
    test_output = "test_pattern_processed.mp4"
    
    try:
        # Create a 2-second test pattern
        (
            ffmpeg
            .input('color=c=blue:s=1080x1920:d=2', f='lavfi')
            .output(test_input, vcodec='libx264', pix_fmt='yuv420p', t=2)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        print("[SUCCESS] Created test pattern.")
        
        # Try to process it using the same filter as our app
        (
            ffmpeg
            .input(test_input)
            .filter('scale', 1080, 1920)
            .output(test_output, vcodec='libx264', crf=23, preset='fast', acodec='aac', pix_fmt='yuv420p')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        print("[SUCCESS] Processed test pattern successfully!")
        
        # Cleanup
        if os.path.exists(test_input): os.remove(test_input)
        if os.path.exists(test_output): os.remove(test_output)
        
        print("\n[COMPLETE] FFmpeg is fully functional and ready!")
        return True
        
    except ffmpeg.Error as e:
        print(f"\n[FAILURE] FFmpeg test failed!")
        print(f"Error details:")
        if e.stderr:
            print(e.stderr.decode())
        else:
            print(str(e))
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = verify_ffmpeg()
    sys.exit(0 if success else 1)

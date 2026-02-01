# Edge TTS Subtitle Dubbing (Numpy/Librosa)

[ 🇹🇷 Türkçe ](README_tr.md)

This tool converts **SRT subtitles** into a single, synchronized **audio file** using Microsoft Edge TTS with sample-accurate audio processing. It uses a strict **Time-Slot Filling** algorithm powered by **Numpy** and **Librosa** to ensure the generated audio perfectly matches the duration of the original video, preventing desynchronization over time.

🔗 [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fr0stb1rd/Edge-TTS-Subtitle-Dubbing/blob/main/Edge_TTS_Subtitle_Dubbing.ipynb) \| [Repo](https://github.com/fr0stb1rd/Edge-TTS-Subtitle-Dubbing) \| [View Audio Processing Pipeline Diagram (Mermaid)](https://fr0stb1rd.gitlab.io/posts/edge-tts-subtitle-dubbing/#audio-processing-pipeline)

## Key Features
*   **Sample-Accurate Synchronization**: Uses Numpy/Librosa for precise, sample-level audio concatenation ensuring perfect timing.
*   **Memory Optimized**: List-based accumulation buffer prevents O(N²) memory copying, making it efficient even for very long videos.
*   **High-Quality Time-Stretching**: Uses `audiostretchy` library for superior audio quality when adjusting speech speed.
*   **Async Batch Processing**: Generates TTS audio in parallel for 2-3x faster processing.
*   **Smart Text Caching**: Automatically reuses audio for identical text segments, saving up to 50% on repetitive content.
*   **Time-Slot Filling Sync**: Ensures every subtitle block takes up exactly the amount of time defined in the SRT, inserting silence if the spoken audio is too short.
*   **Perfect Video Match**: Can pad the final audio to match your video's exact length using `--ref_video`.
*   **Smart Silence**: Inserts calculation-precise silence between lines with sample-level accuracy.
*   **Multi-Language**: Supports all languages and voices provided by Microsoft Edge TTS.
*   **Neural Voices**: Uses high-quality Neural voices like `en-US-JennyNeural`, `tr-TR-AhmetNeural`.
*   **Resume Capability**: Can resume from where it left off if interrupted.
*   **Automatic Late-Start Handling**: Intelligently handles overlapping subtitles by forcing maximum speed compression.
*   **Progress Statistics**: Detailed real-time statistics showing generation, caching, and error counts.

## Prerequisites

*   Python 3.8+
*   **FFmpeg** installed and in PATH (required for `ffprobe` media duration detection)

## Clone and enter directory

```bash
git clone https://github.com/fr0stb1rd/Edge-TTS-Subtitle-Dubbing.git

cd Edge-TTS-Subtitle-Dubbing
```

## Virtual Env (Recommended)
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

## Dependencies

```bash
pip install -r requirements.txt
```

## Usage

Basic command:
```bash
python src/main.py <input.srt> <output.wav> --voice <voice_name>
```

**Example:**
```bash
python src/main.py tr.srt output.wav --voice tr-TR-AhmetNeural
```

### Advanced Options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--voice <name>` | Edge TTS Voice name (Run `edge-tts --list-voices`). | `en-US-JennyNeural` |
| `--ref_video <path>` | Path to original video. Adds silence at the end to match duration exactly. | `None` |
| `--expected_duration <val>` | Manual total duration (Seconds or HH:MM:SS) if video is not available. | `None` |
| `--max_speed <val>` | Max speed-up factor (e.g. 2.0). Increase if you see many 'Overlap' warnings. | `1.5` |
| `--temp <path>` | Specify a custom temporary directory. | `temp/` in current dir |
| `--keep-temp` | Don't delete temporary files after finishing. | `False` (Auto-delete) |
| `--resume` | Resume processing existing temp files. | `False` |
| `--no-concat` | Generate segments only, skip final merge. | `False` |
| `--batch_size <num>` | Number of concurrent TTS requests for parallel processing. | `10` |
| `--log_file <path>` | Path to log file. Auto-creates `<output_name>.log` next to output file if not specified. | Auto-generated |
| `--log_level <level>` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `--retries <num>` | Number of retry attempts for network failures during TTS generation. | `10` |
| `--format <ext>` | Force output format (`wav`, `m4a`, `opus`). Appends extension if needed. | `None` (WAV) |

**Example: Full Synchronization Workflow**
To guarantee the output audio is exactly the same length as your video:

```bash
# Scenario A: You have the video locally
python src/main.py subtitles.srt dub.wav --ref_video original_movie.mp4

# Scenario B: You know the video duration (No video file needed)
# You can provide the duration in "HH:MM:SS" format or total seconds.

# Option 1: HH:MM:SS.mmm (e.g., 1 hour, 30 mins, 5.123 seconds)
python src/main.py subtitles.srt dub.wav --expected_duration "01:30:05.123"

# Option 2: Seconds (e.g., 90 minutes)
python src/main.py subtitles.srt dub.wav --expected_duration 5400.5
```


**Example: Logging Options**
Control logging output and verbosity:

```bash
# Default: Creates output.log with INFO level
python src/main.py subtitles.srt output.wav --voice en-US-JennyNeural

# Custom log file location
python src/main.py subtitles.srt output.wav --log_file ~/logs/dubbing.log

# Debug level for troubleshooting
python src/main.py subtitles.srt output.wav --log_level DEBUG

# Minimal logging (errors only)
python src/main.py subtitles.srt output.wav --log_level ERROR
```

## Utility Tips

### Getting Video Duration with ffprobe
If you need to find the exact duration of a video file for the `--expected_duration` parameter:

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 video.mp4
```

This will output the duration in seconds (e.g., `5400.5`).

### Finding Voices
List all available voices:
```bash
edge-tts --list-voices
```

## Performance Optimizations

The tool includes several optimizations for fast processing:

### Async Batch Processing
**2-3x faster generation** through parallel TTS requests:

```bash
# Default: 10 concurrent requests
python src/main.py subtitles.srt output.wav

# Faster on good networks (20 concurrent)
python src/main.py subtitles.srt output.wav --batch_size 20

# Safer on slow networks (5 concurrent)
python src/main.py subtitles.srt output.wav --batch_size 5
```

**How it works:**
- Segments are generated in parallel batches instead of sequentially
- Configurable batch size to balance speed vs network load
- Progress shown per batch

### Smart Text Caching
**20-75% faster** on files with repeated text:

- Automatically detects identical subtitle text
- Generates TTS once, reuses for all duplicates
- Cache stored in temp directory (auto-cleaned unless `--keep-temp`)

**Example:**
```
100 segments with common phrases:
- "Yes" appears 15 times → Generated once, cached 14 times
- "Thank you" appears 10 times → Generated once, cached 9 times
Result: 25% fewer TTS requests!
```

### Combined Performance
**Expected speed improvements:**
- Small files (< 50 segments): 2-3x faster
- Large files (500+ segments): 3-5x faster
- Repetitive content: Up to 5x faster

## Progress Statistics

The tool provides detailed progress information:

```
============================================================
Processing Summary:
  Total segments: 100
  Generated: 65        # New TTS audio created
  Cached (text reuse): 20   # Duplicates reused from cache
  Resumed: 15         # Existing files from previous run
  Empty subtitles: 2   # Blank subtitle entries
  Failed (using silence): 0
  Overlaps detected: 1
  Late starts (speed-up): 1
  Output audio duration: 3645.23s
  Target match accuracy: 99.97%
============================================================
```

**Statistics explained:**
- **Generated**: Unique TTS audio files created this run
- **Cached**: Segments reused from smart caching (same text)
- **Resumed**: Files from previous interrupted run (with `--resume`)
- **Target match accuracy**: How closely output matches expected duration

## Technical Details

### Audio Processing Pipeline
The tool uses a sophisticated audio processing pipeline for maximum quality and synchronization:

1. **TTS Generation**: Uses Microsoft Edge TTS to generate MP3 audio for each subtitle segment
2. **Time-Stretching**: Uses `audiostretchy` library to adjust audio duration while maintaining quality
3. **Sample-Accurate Concatenation**: Numpy arrays ensure precise timing at the sample level (24kHz)
4. **List-Based Accumulation**: Segments are stored in a list and concatenated once, avoiding O(N²) memory complexity
5. **Exact Trimming/Padding**: Final audio is trimmed or padded to exact sample count to prevent drift

### Memory Optimization
For long videos with many subtitles, the tool uses a list-based buffer instead of repeated `numpy.concatenate()` calls. This prevents performance degradation and memory issues that would occur with the naive approach.

**Memory Usage:**
- Minimal footprint: List-based buffer prevents memory bloat
- Scales linearly with file length
- Tested with 1000+ segment files without issues

### Late-Start Handling
If a subtitle starts late (overlaps with previous audio), the tool automatically:
- Detects the overlap and issues a warning
- Forces maximum speed compression (up to `--max_speed` factor)
- Continues processing to maintain overall synchronization

## Supported Voices (Selection)

| Name | Gender | Category |
| :--- | :--- | :--- |
| **English (US)** | | |
| `en-US-JennyNeural` | Female | General |
| `en-US-ChristopherNeural` | Male | News |
| `en-US-GuyNeural` | Male | News |
| **Turkish** | | |
| `tr-TR-AhmetNeural` | Male | General |
| `tr-TR-EmelNeural` | Female | General |
| **Chinese** | | |
| `zh-CN-XiaoxiaoNeural` | Female | Warm |
| `zh-CN-YunyangNeural` | Male | Professional |

*(Run `edge-tts --list-voices` for the full list)*

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details or visit the [repository](https://github.com/fr0stb1rd/Edge-TTS-Subtitle-Dubbing).

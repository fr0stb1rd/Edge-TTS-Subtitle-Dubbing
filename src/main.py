#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edge TTS Subtitle Dubbing - Convert SRT subtitles to synchronized audio using Edge TTS

Repository: https://github.com/fr0stb1rd/Edge-TTS-Subtitle-Dubbing
SPDX-License-Identifier: MIT
Copyright (c) 2026 fr0stb1rd
"""

import os
import sys
import argparse
import asyncio
import logging
import shutil
import subprocess
import numpy as np
import librosa
import soundfile as sf
import pysrt
import edge_tts
from typing import Optional
import numpy.typing as npt
from tqdm import tqdm
import warnings
import random
# Suppress pydub SyntaxWarning in Python 3.12+ (invalid escape sequence)
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")

from pathlib import Path
from audiostretchy.stretch import stretch_audio

def print_banner():
    """Print application banner with project information."""
    banner = """
╔═══════════════════════════════════════════════════╗
║             Edge TTS Subtitle Dubbing             ║
║  github.com/fr0stb1rd/Edge-TTS-Subtitle-Dubbing   ║
║           License: MIT © 2026 fr0stb1rd           ║
╚═══════════════════════════════════════════════════╝
    """
    print(banner)

logger = logging.getLogger(__name__)

def setup_logging(log_file: Optional[str] = None, log_level: str = "INFO") -> None:
    """Configure logging to console and optionally to file.
    
    Args:
        log_file: Path to log file for persistent logging (optional)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Set logger level
    logger.setLevel(numeric_level)
    
    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if log file specified)
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.info(f"Logging to file: {log_file}")

# Audio Processing Constants
SAMPLE_RATE = 24000  # Edge TTS typically outputs 24kHz
OVERLAP_THRESHOLD = 0.01  # Seconds - threshold for detecting subtitle overlap
MIN_SEGMENT_DURATION = 0.05  # Seconds - minimum duration for late-start segments
FINAL_PADDING_THRESHOLD = 0.01  # Seconds - threshold for adding final padding
EXCESS_AUDIO_WARNING_THRESHOLD = 1.0  # Seconds - threshold for warning about excess audio

def get_media_duration(file_path: Optional[str]) -> float:
    """Get duration of a media file using ffprobe.
    
    Args:
        file_path: Path to media file
        
    Returns:
        Duration in seconds, or 0.0 if file not found or error occurs
    """
    if not file_path:
        logger.warning("No file path provided for duration check")
        return 0.0
    if not os.path.exists(file_path):
        logger.error(f"Media file not found: {file_path}")
        return 0.0
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        duration = float(result.stdout.strip())
        logger.debug(f"Media duration for {os.path.basename(file_path)}: {duration:.2f}s")
        return duration
    except FileNotFoundError:
        logger.error("ffprobe not found. Please install FFmpeg and ensure it's in PATH.")
        return 0.0
    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobe failed for {file_path}: {e.stderr}")
        return 0.0
    except ValueError as e:
        logger.error(f"Invalid duration value from ffprobe: {e}")
        return 0.0
    except Exception as e:
        logger.error(f"Unexpected error reading duration for {file_path}: {e}")
        return 0.0

def parse_duration_str(duration_str: Optional[str]) -> float:
    """Parses duration string (HH:MM:SS or seconds) to seconds.
    
    Args:
        duration_str: Duration as "HH:MM:SS", "MM:SS", or numeric seconds string
        
    Returns:
        Duration in seconds, or 0.0 if invalid format
    """
    if not duration_str:
        return 0.0
    try:
        if ":" in duration_str:
            parts = duration_str.split(":")
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
        else:
            return float(duration_str)
    except Exception as e:
        logger.error(f"Invalid duration format: {duration_str}. Use HH:MM:SS or seconds.")
        return 0.0
    return 0.0

def convert_audio_format(input_path: str, output_path: str, format: str) -> bool:
    """Convert audio file to specified format using ffmpeg.
    
    Args:
        input_path: Path to source audio file
        output_path: Path to destination file
        format: Target format (m4a, opus, wav)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if format == 'm4a':
            # AAC encoding for M4A
            cmd = ["ffmpeg", "-i", input_path, "-c:a", "aac", "-b:a", "192k", "-y", output_path]
        elif format == 'opus':
            # Opus encoding
            cmd = ["ffmpeg", "-i", input_path, "-c:a", "libopus", "-b:a", "128k", "-y", output_path]
        else:
            # Default or WAV, just copy
            cmd = ["ffmpeg", "-i", input_path, "-y", output_path]
            
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.error(f"Failed to convert audio to {format}: {e}")
        return False

def time_str_to_seconds(t_obj) -> float:
    """Convert pysrt time object to seconds.
    
    Args:
        t_obj: pysrt SubRipTime object
        
    Returns:
        Time in seconds as float
    """
    return t_obj.hours * 3600 + t_obj.minutes * 60 + t_obj.seconds + t_obj.milliseconds / 1000.0

async def generate_audio_segment(text: str, output_file: str, voice: str, rate: str = "+0%", retries: int = 10) -> None:
    """Generates audio for a single text segment using Edge TTS with retry logic.
    
    Args:
        text: Text content to convert to speech
        output_file: Path where audio file will be saved
        voice: Edge TTS voice name (e.g., 'en-US-JennyNeural')
        rate: Speech rate adjustment (e.g., '+0%', '+10%', '-10%')
        retries: Number of retry attempts for network failures
    """
    for i in range(retries + 1):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(output_file)
            return
        except Exception as e:
            if i < retries:
                wait_time = (i + 1) * random.uniform(1, 3)
                logger.warning(f"Connection error, retrying in {wait_time:.1f}s... ({i+1}/{retries})")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Failed to generate audio after {retries} retries: {e}")
                raise e


async def generate_audio_batch(
    segments_info: list[tuple[str, str, int]],
    voice: str,
    batch_size: int = 10,
    retries: int = 10
) -> dict[int, Optional[Exception]]:
    """Generate multiple audio segments in parallel using async batch processing.
    
    Args:
        segments_info: List of tuples (text, output_path, segment_index)
        voice: Edge TTS voice name
        batch_size: Number of concurrent requests (default: 10)
        
    Returns:
        Dictionary mapping segment index to Exception (if failed) or None (if success)
    """
    async def generate_one(text: str, output_path: str, index: int) -> tuple[int, Optional[Exception]]:
        try:
            await generate_audio_segment(text, output_path, voice, retries=retries)
            return (index, None)
        except Exception as e:
            return (index, e)
    
    all_results = {}
    
    # Process in batches to avoid overwhelming the API
    for i in range(0, len(segments_info), batch_size):
        batch = segments_info[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(segments_info) + batch_size - 1) // batch_size
        
        logger.info(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} segments)...")
        
        # Generate batch in parallel
        tasks = [generate_one(text, path, idx) for text, path, idx in batch]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        # Collect results
        for idx, error in results:
            all_results[idx] = error
    
    return all_results

def adjust_audio_length(
    wav_path: str, 
    desired_length: float, 
    sample_rate: int = SAMPLE_RATE, 
    max_speed_factor: float = 1.5
) -> npt.NDArray[np.float32]:
    """Adjusts audio file to desired length using audiostretchy time-stretching.
    
    Args:
        wav_path: Path to input audio file (MP3 or WAV)
        desired_length: Target duration in seconds
        sample_rate: Audio sample rate in Hz
        max_speed_factor: Maximum speed-up factor (e.g., 2.0 = 2x speed)
        
    Returns:
        Adjusted audio as numpy float32 array at specified sample rate
        
    Note:
        Uses high-quality time-stretching algorithm. Automatically cleans up
        temporary files. Returns original audio if stretching fails.
    """
    try:
        # Load original
        y, sr = librosa.load(wav_path, sr=sample_rate)
    except Exception as e:
        logger.error(f"Failed to load {wav_path}: {e}")
        return np.zeros(0, dtype=np.float32)

    current_length = len(y) / sample_rate
    
    if desired_length <= 0:
        return y

    # Calculate time-stretching ratio
    # audiostretchy ratio: >1 slows down, <1 speeds up
    # ratio = desired_duration / current_duration
    ratio = desired_length / current_length
    
    # Clamp ratio to prevent excessive speed-up
    # max_speed 2.0x means minimum ratio of 0.5
    min_ratio = 1.0 / max_speed_factor
    if ratio < min_ratio:
        ratio = min_ratio
        logger.warning(f"  Clamped max speed: Ratio {ratio:.3f} (Req: {desired_length:.2f}s from {current_length:.2f}s)")
    
    input_tmp = wav_path
    output_tmp = wav_path.replace(".mp3", "_stretched.wav").replace(".wav", "_stretched.wav")
    
    try:
        stretch_audio(input_tmp, output_tmp, ratio=ratio, sample_rate=sample_rate)
        # Load the result
        y_stretched, _ = librosa.load(output_tmp, sr=sample_rate)
        
        # Trim or Pad to EXACT desired sample count to avoid drift
        target_samples = int(desired_length * sample_rate)
        
        if len(y_stretched) < target_samples:
            # Pad
            padding = target_samples - len(y_stretched)
            y_stretched = np.pad(y_stretched, (0, padding), 'constant')
        elif len(y_stretched) > target_samples:
            # Crop
            y_stretched = y_stretched[:target_samples]
            
        return y_stretched
        
    except Exception as e:
        logger.error(f"Stretching failed: {e}")
        return y
    finally:
        # Clean up temporary stretched file
        if os.path.exists(output_tmp):
            try:
                os.remove(output_tmp)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {output_tmp}: {e}")

def srt_to_audio_numpy(
    srt_path: str,
    output_path: str,
    voice: str,
    temp_dir: Optional[str] = None,
    keep_temp: bool = False,
    resume: bool = False,
    ref_video: Optional[str] = None,
    expected_duration: Optional[str] = None,
    max_speed: float = 1.5,
    log_file: Optional[str] = None,
    log_level: str = "INFO",
    no_concat: bool = False,
    batch_size: int = 10,
    retries: int = 10
) -> None:
    """Convert SRT subtitles to synchronized audio using Edge TTS.
    
    Main processing function with sample-accurate synchronization using Numpy/Librosa.
    Optimized for long files using list-based accumulation buffer.
    
    Args:
        srt_path: Path to input SRT subtitle file
        output_path: Path for output WAV audio file
        voice: Edge TTS voice name (e.g., 'en-US-JennyNeural')
        temp_dir: Custom temporary directory (auto-generated if None)
        keep_temp: If True, preserve temporary files after completion
        resume: If True, resume from existing temp files
        ref_video: Path to reference video for duration matching
        expected_duration: Target duration as "HH:MM:SS" or seconds string
        max_speed: Maximum speed-up factor (e.g., 1.5 = 1.5x speed max)
        log_file: Path to log file (auto-generated if None)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        no_concat: If True, generate segments only without final merge
        batch_size: Number of concurrent TTS requests (default: 10)
        
    Returns:
        None. Outputs audio file to output_path (unless no_concat is True).
    """
    # Setup logging
    setup_logging(log_file, log_level)
    
    # Validate input file
    if not os.path.exists(srt_path):
        logger.error(f"SRT file not found: {srt_path}")
        return
    
    # Validate and create output directory
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Created output directory: {output_dir}")
        except Exception as e:
            logger.error(f"Failed to create output directory {output_dir}: {e}")
            return

    # Prepare temp dir
    if not temp_dir:
        import hashlib
        with open(srt_path, 'rb') as f:
            file_content = f.read()
        h = hashlib.md5(file_content).hexdigest()
        temp_dir = os.path.join(os.getcwd(), "temp", h)
    
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
    
    logger.info(f"Working in temp ID: {os.path.basename(temp_dir)}")

    # Parse SRT file with robust error handling
    try:
        subs = pysrt.open(srt_path, encoding='utf-8')
    except UnicodeDecodeError:
        # Try alternative encodings
        try:
            subs = pysrt.open(srt_path, encoding='latin-1')
            logger.warning("SRT file parsed with latin-1 encoding")
        except Exception as e:
            logger.error(f"Failed to parse SRT file with alternative encoding: {e}")
            return
    except Exception as e:
        logger.error(f"Failed to parse SRT file: {e}")
        return
    
    # Validate SRT content
    if not subs or len(subs) == 0:
        logger.error("SRT file is empty or contains no valid subtitles")
        return
    
    logger.info(f"Loaded {len(subs)} subtitle entries")
    
    # Use a list to store chunks, avoiding O(N^2) copying
    audio_segments = []
    current_total_samples = 0
    
    # Determine Final Target Duration
    final_target_sec = 0.0
    if expected_duration:
        final_target_sec = parse_duration_str(expected_duration)
    elif ref_video:
        final_target_sec = get_media_duration(ref_video)
        
    logger.info(f"Final Target Duration: {final_target_sec}s")
    logger.info(f"Starting processing of {len(subs)} subtitle segments...")
    logger.info("="*60)
    
    # Create cache directory for text-based caching
    cache_dir = os.path.join(temp_dir, "cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    
    # Statistics tracking
    stats = {
        'total': len(subs),
        'generated': 0,
        'resumed': 0,
        'cached': 0,
        'failed': 0,
        'empty': 0,
        'overlaps': 0,
        'late_starts': 0
    }
    
    # First pass: Collect segments that need generation
    segments_to_generate = []  # List of (text, output_path, segment_index)
    text_to_cache = {}  # Map text hash to cache path for deduplication
    
    for i, sub in enumerate(subs):
        text = sub.text.replace('\n', ' ').strip()
        if not text:
            stats['empty'] += 1
            continue
            
        raw_audio_path = os.path.join(temp_dir, f"raw_{i}.mp3")
        exists = os.path.exists(raw_audio_path) and os.path.getsize(raw_audio_path) > 0
        
        if resume and exists:
            stats['resumed'] += 1
        else:
            # Check cache for this text
            import hashlib
            text_hash = hashlib.md5(text.lower().encode('utf-8')).hexdigest()
            cache_path = os.path.join(cache_dir, f"cache_{text_hash}.mp3")
            
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                # Use cached audio
                try:
                    import shutil
                    shutil.copy2(cache_path, raw_audio_path)
                    stats['cached'] += 1
                    logger.debug(f"Using cached audio for segment {i} (hash: {text_hash[:8]}...)")
                except Exception as e:
                    logger.warning(f"Failed to copy cache for segment {i}: {e}")
                    # Fall through to generation
                    if text not in text_to_cache:
                        text_to_cache[text] = cache_path
                        segments_to_generate.append((text, cache_path, i))
            else:
                # Need to generate and cache
                if text not in text_to_cache:
                    text_to_cache[text] = cache_path
                    segments_to_generate.append((text, cache_path, i))
    
    # Batch generate all needed segments in parallel
    if segments_to_generate:
        unique_count = len(segments_to_generate)
        total_needed = sum(1 for i, sub in enumerate(subs) 
                          if not (resume and os.path.exists(os.path.join(temp_dir, f"raw_{i}.mp3"))))
        deduped = total_needed - unique_count
        
        if deduped > 0:
            logger.info(f"Deduplicated {deduped} identical text segments")
        
        logger.info(f"Generating {unique_count} unique audio segments (batch size: {batch_size})...")
        generation_errors = asyncio.run(generate_audio_batch(segments_to_generate, voice, batch_size, retries))
        
        # Copy cached files to segment locations and count results
        for text, cache_path, idx in segments_to_generate:
            raw_audio_path = os.path.join(temp_dir, f"raw_{idx}.mp3")
            
            if idx in generation_errors and generation_errors[idx] is None:
                # Generation successful, copy from cache to raw location
                try:
                    import shutil
                    if os.path.exists(cache_path):
                        shutil.copy2(cache_path, raw_audio_path)
                    stats['generated'] += 1
                except Exception as e:
                    logger.error(f"Failed to copy generated cache for segment {idx}: {e}")
                    stats['failed'] += 1
            else:
                # Generation failed
                stats['failed'] += 1
                if idx in generation_errors:
                    logger.error(f"Failed to generate audio for segment {idx}: {generation_errors[idx]}")
    # Now copy/deduplicate for all segments that need this text
    logger.info("Copying cached audio to segment locations...")
    for i, sub in enumerate(subs):
        text = sub.text.replace('\n', ' ').strip()
        if not text:
            continue
            
        raw_audio_path = os.path.join(temp_dir, f"raw_{i}.mp3")
        
        # Skip if already exists (resumed)
        if os.path.exists(raw_audio_path) and os.path.getsize(raw_audio_path) > 0:
            continue
        
        # Get cache path for this text
        import hashlib
        text_hash = hashlib.md5(text.lower().encode('utf-8')).hexdigest()
        cache_path = os.path.join(cache_dir, f"cache_{text_hash}.mp3")
        
        # Copy from cache to segment location
        if os.path.exists(cache_path):
            try:
                import shutil
                shutil.copy2(cache_path, raw_audio_path)
            except Exception as e:
                logger.error(f"Failed to copy cache to segment {i}: {e}")
    
    logger.info("Processing and synchronizing segments...")

    for i, sub in enumerate(tqdm(subs, desc="Processing", unit="sub")):
        start_sec = time_str_to_seconds(sub.start)
        end_sec = time_str_to_seconds(sub.end)
        target_span_sec = end_sec - start_sec
        text = sub.text.replace('\n', ' ').strip()
        
        # 1. Handle Pre-Gap (Silence before this sub)
        current_head_sec = current_total_samples / SAMPLE_RATE
        gap_sec = start_sec - current_head_sec
        
        if gap_sec > 0:
            # Add silence
            gap_samples = int(gap_sec * SAMPLE_RATE)
            silence_chunk = np.zeros(gap_samples, dtype=np.float32)
            audio_segments.append(silence_chunk)
            current_total_samples += gap_samples
            
        elif gap_sec < -OVERLAP_THRESHOLD:
            stats['overlaps'] += 1
            logger.warning(f"Overlap at sub {i+1}: Head {current_head_sec:.2f}s > Start {start_sec:.2f}s")
            # We continue from where we are.

        if not text:
            stats['empty'] += 1
            # Fill slot with silence to reach end_sec
            current_head_sec = current_total_samples / SAMPLE_RATE
            needed_sec = end_sec - current_head_sec
            if needed_sec > 0:
                needed_samples = int(needed_sec * SAMPLE_RATE)
                audio_segments.append(np.zeros(needed_samples, dtype=np.float32))
                current_total_samples += needed_samples
            continue

        # 2. Get Generated Audio (already created in batch or from cache)
        raw_audio_path = os.path.join(temp_dir, f"raw_{i}.mp3")
        
        # Check if generation failed
        if i in generation_errors and generation_errors[i] is not None:
            # Use silence as fallback for failed generation
            logger.debug(f"Using silence fallback for segment {i+1}")
            needed_samples = int(target_span_sec * SAMPLE_RATE)
            audio_segments.append(np.zeros(needed_samples, dtype=np.float32))
            current_total_samples += needed_samples
            continue
            
        # 3. Process & Fit
        current_head_sec = current_total_samples / SAMPLE_RATE
        target_dur_for_segment = end_sec - current_head_sec
        
        if target_dur_for_segment < MIN_SEGMENT_DURATION:
            stats['late_starts'] += 1
            # We are late. Force max speed compression by requesting very small duration.
            logger.warning(f"  Sub {i+1} starts late. Forcing max speed catch-up.")
            target_dur_for_segment = MIN_SEGMENT_DURATION 
        
        # Adjust audio
        stretched_wav = adjust_audio_length(
            raw_audio_path, 
            target_dur_for_segment, 
            sample_rate=SAMPLE_RATE, 
            max_speed_factor=max_speed
        )
        
        audio_segments.append(stretched_wav)
        current_total_samples += len(stretched_wav)
        
    # 3. Final Padding (Ref Video)
    if final_target_sec > 0:
        current_len_sec = current_total_samples / SAMPLE_RATE
        missing = final_target_sec - current_len_sec
        
        if missing > FINAL_PADDING_THRESHOLD:
            logger.info(f"Adding final padding: {missing:.2f}s")
            pad_samples = int(missing * SAMPLE_RATE)
            audio_segments.append(np.zeros(pad_samples, dtype=np.float32))
            current_total_samples += pad_samples
        elif missing < -EXCESS_AUDIO_WARNING_THRESHOLD:
            logger.warning(f"Total audio ({current_len_sec:.2f}s) exceeds target ({final_target_sec:.2f}s)!")
            
    # 4. Concatenate & Export
    logger.info("="*60)
    logger.info("Processing Summary:")
    logger.info(f"  Total segments: {stats['total']}")
    logger.info(f"  Generated: {stats['generated']}")
    logger.info(f"  Cached (text reuse): {stats['cached']}")
    logger.info(f"  Resumed: {stats['resumed']}")
    logger.info(f"  Empty subtitles: {stats['empty']}")
    logger.info(f"  Failed (using silence): {stats['failed']}")
    if stats['overlaps'] > 0:
        logger.info(f"  Overlaps detected: {stats['overlaps']}")
    if stats['late_starts'] > 0:
        logger.info(f"  Late starts (speed-up): {stats['late_starts']}")
    
    final_audio_duration = current_total_samples / SAMPLE_RATE
    logger.info(f"  Output audio duration: {final_audio_duration:.2f}s")
    if final_target_sec > 0:
        accuracy = (final_audio_duration / final_target_sec * 100) if final_target_sec > 0 else 0
        logger.info(f"  Target match accuracy: {accuracy:.2f}%")
    logger.info("="*60)
    
    # 4. Concatenate & Export
    if no_concat:
        logger.info("Skipping concatenation (--no-concat mode)")
        logger.info(f"Individual segments saved in: {temp_dir}")
        logger.info("Done.")
        return
    
    logger.info("Concatenating segments...")
    if audio_segments:
        full_wav = np.concatenate(audio_segments)
    else:
        full_wav = np.zeros(0, dtype=np.float32)
    
    try:
        output_ext = Path(output_path).suffix.lower().lstrip('.')
    except:
        output_ext = 'wav'
    
    if output_ext in ['m4a', 'opus']:
        logger.info(f"Saving temporary WAV for conversion to {output_ext}...")
        temp_output_wav = os.path.join(temp_dir, "final_output_temp.wav")
        sf.write(temp_output_wav, full_wav, SAMPLE_RATE)
        
        logger.info(f"Converting to {output_ext}...")
        if convert_audio_format(temp_output_wav, output_path, output_ext):
            logger.info("Done.")
        else:
            logger.error("Conversion failed.")
            
        # Clean up temp wav
        if os.path.exists(temp_output_wav):
            try:
                os.remove(temp_output_wav)
            except: pass
    else:
        logger.info(f"Saving final output to {output_path} ...")
        sf.write(output_path, full_wav, SAMPLE_RATE)
        logger.info("Done.")
    
    # Cleanup
    if not keep_temp and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        logger.info("Cleaned temp (including cache).")
    elif keep_temp:
        cache_dir = os.path.join(temp_dir, "cache")
        if os.path.exists(cache_dir):
            cache_count = len([f for f in os.listdir(cache_dir) if f.startswith('cache_')])
            logger.info(f"Cache preserved: {cache_count} unique text segments in {cache_dir}")

if __name__ == "__main__":
    # Print banner
    print_banner()
    
    parser = argparse.ArgumentParser(description="SRT to Audio (Numpy/Librosa Precise Sync)")
    parser.add_argument("srt_file")
    parser.add_argument("output_file")
    parser.add_argument("--voice", default="en-US-JennyNeural")
    parser.add_argument("--temp", default=None)
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--ref_video", default=None)
    parser.add_argument("--expected_duration", default=None)
    parser.add_argument("--max_speed", type=float, default=1.5)
    parser.add_argument("--log_file", default=None, help="Path to log file. If not specified, creates one next to output file.")
    parser.add_argument("--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging level (default: INFO)")
    parser.add_argument("--no-concat", action="store_true", help="Generate segments only, skip final merge")
    parser.add_argument("--batch_size", type=int, default=10, help="Number of concurrent TTS requests (default: 10)")
    parser.add_argument("--retries", type=int, default=10, help="Number of retry attempts for network failures (default: 10)")
    parser.add_argument("--format", choices=['wav', 'm4a', 'opus'], default=None, help="Output format (wav, m4a, opus). Overrides filename extension if specified.")
    
    args = parser.parse_args()
    
    # Auto-generate log file path if not specified
    log_file = args.log_file
    if log_file is None:
        output_dir = os.path.dirname(os.path.abspath(args.output_file))
        output_basename = os.path.splitext(os.path.basename(args.output_file))[0]
        log_file = os.path.join(output_dir, f"{output_basename}.log")
        
    # Handle format override
    final_output = args.output_file
    if args.format:
        path = Path(final_output)
        if path.suffix.lower().lstrip('.') != args.format:
            final_output = f"{final_output}.{args.format}"
            print(f"Output filename changed to match format: {final_output}")
    
    srt_to_audio_numpy(
        args.srt_file, 
        final_output, 
        args.voice, 
        temp_dir=args.temp, 
        keep_temp=args.keep_temp, 
        resume=args.resume, 
        ref_video=args.ref_video,
        expected_duration=args.expected_duration,
        max_speed=args.max_speed,
        log_file=log_file,
        log_level=args.log_level,
        no_concat=args.no_concat,
        batch_size=args.batch_size,
        retries=args.retries
    )

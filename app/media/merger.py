"""
Video Merger Module for Crash Out Multi-Agent Pipeline.
Concatenates sequential 15-second scene MP4 clips into a single 60-second master episode
using FFmpeg via imageio-ffmpeg with strict audio/video synchronization and 9:16 vertical formatting.
"""
import os
import subprocess
import time
from typing import List, Dict, Any, Optional
import imageio_ffmpeg

def merge_scene_videos(scene_video_paths: List[str], output_path: str) -> Dict[str, Any]:
    """
    Concatenates a list of scene MP4 files into a single merged master video.
    
    Args:
        scene_video_paths: List of absolute file paths to sequential scene MP4s (e.g. 4 clips).
        output_path: Absolute destination path for the merged master MP4.
        
    Returns:
        Dict with status, output_path, duration_sec, file_size_bytes, and error if any.
    """
    start_time = time.time()
    
    if not scene_video_paths:
        return {"success": False, "error": "No scene video paths provided for merging."}
    
    # Verify all input files exist
    valid_paths = []
    for p in scene_video_paths:
        if p and os.path.exists(p) and os.path.getsize(p) > 1000:
            valid_paths.append(p)
        else:
            return {
                "success": False,
                "error": f"Scene video file missing or empty: {p}"
            }
            
    num_scenes = len(valid_paths)
    if num_scenes == 0:
        return {"success": False, "error": "No valid scene video files to merge."}

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Ensure destination directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Construct FFmpeg command using filter_complex for seamless audio & video concat
    # Command template:
    # ffmpeg -y -i s1.mp4 -i s2.mp4 ... -filter_complex "[0:v:0][0:a:0][1:v:0][1:a:0]...concat=n=N:v=1:a=1[outv][outa]"
    # -map "[outv]" -map "[outa]" -c:v libx264 -preset fast -pix_fmt yuv420p -c:a aac -b:a 192k output.mp4
    
    cmd = [ffmpeg_exe, "-y"]
    filter_inputs = ""
    
    for idx, path in enumerate(valid_paths):
        cmd.extend(["-i", path])
        filter_inputs += f"[{idx}:v:0][{idx}:a:0]"
        
    filter_complex = f"{filter_inputs}concat=n={num_scenes}:v=1:a=1[outv][outa]"
    
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ])
    
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180
        )
        
        if proc.returncode != 0:
            # If complex filter failed (e.g. if an input file has no audio stream), try fallback method
            print(f"Filter complex concat notice: {proc.stderr[-300:] if proc.stderr else 'Unknown'}. Trying concat demuxer fallback...")
            return _merge_via_demuxer(ffmpeg_exe, valid_paths, output_path, start_time)
            
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 5000:
            return {
                "success": False,
                "error": f"Merged file creation failed or produced tiny output ({os.path.getsize(output_path) if os.path.exists(output_path) else 0} bytes)."
            }
            
        file_size = os.path.getsize(output_path)
        latency = round(time.time() - start_time, 2)
        
        return {
            "success": True,
            "output_path": output_path,
            "file_size_bytes": file_size,
            "file_size_kb": file_size // 1024,
            "scenes_merged": num_scenes,
            "latency_sec": latency,
            "method": "filter_complex"
        }
        
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "FFmpeg merge process timed out after 180 seconds."}
    except Exception as e:
        return {"success": False, "error": f"Exception during video merge: {str(e)}"}

def _merge_via_demuxer(ffmpeg_exe: str, paths: List[str], output_path: str, start_time: float) -> Dict[str, Any]:
    """Fallback concat method using FFmpeg's concat demuxer file list."""
    temp_list_path = os.path.join(os.path.dirname(output_path), f"concat_list_{int(time.time())}.txt")
    try:
        with open(temp_list_path, "w", encoding="utf-8") as f:
            for p in paths:
                # Format path safely for ffmpeg concat demuxer
                safe_p = p.replace("\\", "/")
                f.write(f"file '{safe_p}'\n")
                
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", temp_list_path,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]
        
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
        
        if os.path.exists(temp_list_path):
            os.remove(temp_list_path)
            
        if proc.returncode != 0 or not os.path.exists(output_path):
            return {
                "success": False,
                "error": f"Concat demuxer failed: {proc.stderr[-300:] if proc.stderr else 'Unknown'}"
            }
            
        file_size = os.path.getsize(output_path)
        latency = round(time.time() - start_time, 2)
        return {
            "success": True,
            "output_path": output_path,
            "file_size_bytes": file_size,
            "file_size_kb": file_size // 1024,
            "scenes_merged": len(paths),
            "latency_sec": latency,
            "method": "concat_demuxer"
        }
    except Exception as e:
        if os.path.exists(temp_list_path):
            os.remove(temp_list_path)
        return {"success": False, "error": f"Demuxer fallback error: {str(e)}"}


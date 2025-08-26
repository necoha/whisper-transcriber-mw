# backend/subtitles.py
from typing import List, Dict
import re

def format_timestamp_srt(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

def format_timestamp_vtt(seconds: float) -> str:
    """Convert seconds to WebVTT timestamp format (HH:MM:SS.mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecs:03d}"

def segments_to_srt(segments: List[Dict]) -> str:
    """Convert segments to SRT format"""
    srt_content = []
    
    for i, segment in enumerate(segments, 1):
        start_time = format_timestamp_srt(segment['start'])
        end_time = format_timestamp_srt(segment['end'])
        text = segment['text'].strip()
        
        if not text:
            continue
            
        # Clean up text (remove extra whitespace, handle line breaks)
        text = re.sub(r'\s+', ' ', text)
        
        srt_content.append(f"{i}")
        srt_content.append(f"{start_time} --> {end_time}")
        srt_content.append(text)
        srt_content.append("")  # Empty line between entries
    
    return "\n".join(srt_content)

def segments_to_vtt(segments: List[Dict]) -> str:
    """Convert segments to WebVTT format"""
    vtt_content = ["WEBVTT", ""]
    
    for segment in segments:
        start_time = format_timestamp_vtt(segment['start'])
        end_time = format_timestamp_vtt(segment['end'])
        text = segment['text'].strip()
        
        if not text:
            continue
            
        # Clean up text (remove extra whitespace, handle line breaks)
        text = re.sub(r'\s+', ' ', text)
        
        vtt_content.append(f"{start_time} --> {end_time}")
        vtt_content.append(text)
        vtt_content.append("")  # Empty line between entries
    
    return "\n".join(vtt_content)

def segments_to_txt(segments: List[Dict]) -> str:
    """Convert segments to plain text with timestamps"""
    txt_content = []
    
    for segment in segments:
        start_time = format_timestamp_srt(segment['start'])
        end_time = format_timestamp_srt(segment['end'])
        text = segment['text'].strip()
        
        if not text:
            continue
            
        txt_content.append(f"[{start_time} --> {end_time}] {text}")
    
    return "\n".join(txt_content)
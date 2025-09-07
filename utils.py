"""
Shared utility functions for RoboResume
"""

import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs
import glob
import zipfile


def sanitize_for_path(text: str, max_len: int = 50, style: str = 'descriptive') -> str:
    """
    Sanitize text for use in file/directory names.
    EXTRACTED FROM jobbot resume_pipeline.py _sanitize_for_path function
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Remove or replace problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    sanitized = re.sub(r'_+', '_', sanitized)
    sanitized = sanitized.strip('_.')
    
    if style == 'compact':
        # More aggressive shortening for compact names
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', sanitized)
        max_len = min(max_len, 15)
    
    return sanitized[:max_len] if sanitized else "item"


def create_session_directory(output_base_dir: str, company: str, position: str) -> str:
    """
    Creates a unique, timestamped directory for a new session.
    EXTRACTED FROM jobbot resume_pipeline.py step_0_create_session_directory
    """
    safe_company = sanitize_for_path(company, max_len=15, style='compact') or "company"
    safe_position = sanitize_for_path(position, max_len=20, style='compact') or "position"
    datestamp = datetime.now().strftime("%y%m%d%H%M%S")
    
    unique_folder_name = f"{datestamp}_{safe_company}_{safe_position}_{os.urandom(4).hex()}"

    session_path = os.path.join(output_base_dir, unique_folder_name)
    os.makedirs(session_path, exist_ok=True)
    print(f"📁 Session directory created: {session_path}")
    return unique_folder_name


def cleanup_old_sessions(base_dir: str, days: int = 30) -> None:
    """Remove sessions older than specified days."""
    if not os.path.exists(base_dir):
        return
        
    cutoff = datetime.now() - timedelta(days=days)
    
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path):
            # Check if directory is older than cutoff
            dir_time = datetime.fromtimestamp(os.path.getctime(item_path))
            if dir_time < cutoff:
                try:
                    shutil.rmtree(item_path)
                    print(f"🗑️ Cleaned up old session: {item}")
                except Exception as e:
                    print(f"⚠️ Could not remove {item}: {e}")


def ensure_directory_exists(directory_path: str) -> None:
    """Ensure a directory exists, create if not."""
    os.makedirs(directory_path, exist_ok=True)


def transform_workopolis_url(url: str) -> str:
    """
    Checks if a URL is a Workopolis search URL and transforms it into a direct
    viewjob URL if it contains a 'job' parameter.
    """
    try:
        if "workopolis.com/search" not in url:
            return url

        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        job_id = query_params.get('job', [None])[0]

        if job_id:
            new_url = f"https://www.workopolis.com/jobsearch/viewjob/{job_id}"
            return new_url
        else:
            return url
            
    except Exception:
        return url

def create_session_zip(session_path: str, zip_path: str) -> Optional[str]:
    """
    Creates a zip archive of the session's important files (.md, .json, .pdf).
    """
    try:
        files_to_zip = []
        for extension in ["*.md", "*.json", "*.pdf"]:
            files_to_zip.extend(glob.glob(os.path.join(session_path, extension)))

        if not files_to_zip:
            return None

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in files_to_zip:
                # Add file to zip, using just the filename as the archive name
                zipf.write(file, os.path.basename(file))
        
        return zip_path
    except Exception as e:
        print(f"Error creating zip file: {e}")
        return None


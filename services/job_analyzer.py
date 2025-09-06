"""
Job analysis service - handles content fetching and job posting analysis
EXTRACTED FROM jobbot resume_pipeline.py (steps 1 & 2)
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional
from openai import OpenAI

# Third-party imports
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# Local imports
from models import JobListing
from config import ANALYSIS_PROMPT_TEXT


async def fetch_job_content(source_config: dict, session_path: str) -> str:
    """
    Fetches job content and saves it as job_posting.md in the session folder.
    EXTRACTED FROM jobbot resume_pipeline.py step_1_get_content
    """
    print("\n=== Step 1: Loading Job Posting ===")
    content = await _get_job_content_from_source(source_config)
    if not content:
        raise ValueError("Failed to load job posting content.")
    
    output_path = os.path.join(session_path, "job_posting.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"📄 Job content saved to: {output_path}")
    return output_path


def analyze_job_posting(session_path: str, client: OpenAI, model_name: str) -> str:
    """
    Reads job_posting.md, analyzes it, and saves the result as structured_job_data.json.
    EXTRACTED FROM jobbot resume_pipeline.py step_2_analyze_job
    """
    print("\n=== Step 2: Analyzing Job Posting ===")
    markdown_path = os.path.join(session_path, "job_posting.md")
    with open(markdown_path, "r", encoding="utf-8") as f:
        content = f.read()

    structured_data = _run_job_analysis(content, client, model_name)
    if not structured_data:
        raise ValueError("Failed to analyze job posting.")

    output_path = os.path.join(session_path, "structured_job_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(structured_data.model_dump_json(indent=4))
    
    print(f"📊 Job analysis saved to: {output_path}")
    return output_path


# ============================================================================
# HELPER FUNCTIONS (EXTRACTED FROM jobbot resume_pipeline.py)
# ============================================================================

async def _get_job_content_from_source(source_config: dict) -> Optional[str]:
    """
    Retrieves job content from URL or string source.
    EXTRACTED FROM jobbot resume_pipeline.py
    """
    source_type = source_config.get("type")
    
    if source_type == "url":
        url = source_config.get("url")
        if not url:
            print("❌ Error: No URL provided.")
            return None
        return await _scrape_job_posting_from_url(url)
    
    elif source_type == "string":
        text = source_config.get("text")
        if not text:
            print("❌ Error: No text provided.")
            return None
        return text.strip()
    
    else:
        print(f"❌ Error: Unsupported source type: {source_type}")
        return None


async def _scrape_job_posting_from_url(url: str) -> Optional[str]:
    """
    Scrapes job posting content from a URL using Crawl4AI.
    EXTRACTED FROM jobbot resume_pipeline.py
    """
    try:
        print(f"🌐 Scraping job posting from: {url}")
        
        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )
        
        crawl_config = CrawlerRunConfig(
            markdown_generator=DefaultMarkdownGenerator(),
            word_count_threshold=1,
            only_text=True,
            remove_overlay_elements=True,
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawl_config)
            
            if result.success and result.markdown:
                print("✅ Successfully scraped job posting.")
                return result.markdown.strip()
            else:
                print(f"❌ Failed to scrape content. Status: {result.status_code}")
                return None
                
    except Exception as e:
        print(f"❌ Error during scraping: {str(e)}")
        return None


def _run_job_analysis(content: str, client: OpenAI, model_name: str) -> Optional[JobListing]:
    """
    Runs AI analysis on job posting content.
    EXTRACTED FROM jobbot resume_pipeline.py
    """
    try:
        print("🤖 Running AI analysis on job posting...")
        
        response = client.chat.completions.create(
            model=model_name,
            response_model=JobListing,
            messages=[
                {
                    "role": "system", 
                    "content": ANALYSIS_PROMPT_TEXT
                },
                {
                    "role": "user", 
                    "content": f"Please analyze this job posting and extract structured data:\n\n{content}"
                }
            ],
            max_tokens=4096,
            temperature=0.2
        )
        
        print("✅ Job analysis completed successfully.")
        return response
        
    except Exception as e:
        print(f"❌ Error during job analysis: {str(e)}")
        return None


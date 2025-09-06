"""
Resume tailoring service - handles resume customization
EXTRACTED FROM jobbot resume_pipeline.py (step 3)
"""

import os
import json
from typing import Dict, Any, Optional, Tuple, List
from openai import OpenAI

# Local imports
from models import JobListing, TailoredResumeContent
from config import TAILORING_PROMPT_TEXT


def tailor_resume(session_path: str, base_resume_path: str, client: OpenAI, model_name: str, api_parameters: dict, keywords: List[str]) -> str:
    """
    Reads job data, tailors the resume, and saves it as tailored_resume_content.json.
    EXTRACTED FROM jobbot resume_pipeline.py step_3_tailor_resume
    """
    print("\n=== Step 3: Tailoring Resume ===")
    job_data_path = os.path.join(session_path, "structured_job_data.json")
    with open(job_data_path, "r", encoding="utf-8") as f:
        job_data = JobListing.model_validate_json(f.read())

    tailoring_result, _ = _run_resume_tailoring(job_data, base_resume_path, client, model_name, api_parameters, keywords)
    if not tailoring_result:
        raise ValueError("Failed to tailor resume.")

    output_path = os.path.join(session_path, "tailored_resume_content.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(tailoring_result.model_dump_json(indent=4))

    print(f"✏️ Tailored resume content saved to: {output_path}")
    return output_path


# ============================================================================
# HELPER FUNCTIONS (EXTRACTED FROM jobbot resume_pipeline.py)
# ============================================================================

def _run_resume_tailoring(job_data: JobListing, base_resume_path: str, client: OpenAI, model_name: str, api_parameters: dict, keywords: List[str]) -> Tuple[Optional[TailoredResumeContent], Optional[str]]:
    """
    Runs AI-powered resume tailoring.
    EXTRACTED FROM jobbot resume_pipeline.py
    """
    try:
        print("🤖 Running AI-powered resume tailoring...")
        
        # Load base resume
        with open(base_resume_path, "r", encoding="utf-8") as f:
            base_resume = json.load(f)
        
        # Dynamically inject keywords into the prompt if they exist
        keyword_injection_prompt = ""
        if keywords:
            print(f"Injecting keywords into prompt: {keywords}")
            keyword_list = ", ".join(keywords)
            keyword_injection_prompt = f"\n\n**Keyword Focus:** You MUST strategically incorporate the following keywords, which were extracted from the job description, into the rewritten bullet points: {keyword_list}"

        # Prepare the prompt
        job_description = _format_job_data_for_prompt(job_data)
        base_resume_text = json.dumps(base_resume, indent=2)
        
        full_prompt = f"""
{TAILORING_PROMPT_TEXT}{keyword_injection_prompt}

**Job Description:**
{job_description}

**Base Resume (JSON):**
{base_resume_text}

Please provide a tailored resume in the exact same JSON structure, optimized for this specific job.
"""
        
        response = client.chat.completions.create(
            model=model_name,
            response_model=TailoredResumeContent,
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert resume writer. Transform the provided resume to target the specific job while maintaining accuracy."
                },
                {
                    "role": "user", 
                    "content": full_prompt
                }
            ],
            **api_parameters
        )
        
        print("✅ Resume tailoring completed successfully.")
        return response, None
        
    except Exception as e:
        error_msg = f"❌ Error during resume tailoring: {str(e)}"
        print(error_msg)
        return None, error_msg


def _format_job_data_for_prompt(job_data: JobListing) -> str:
    """
    Formats job data for AI prompt.
    EXTRACTED FROM jobbot resume_pipeline.py
    """
    job_info = []
    
    if job_data.company_name:
        job_info.append(f"Company: {job_data.company_name}")
    if job_data.position_title:
        job_info.append(f"Position: {job_data.position_title}")
    if job_data.location:
        job_info.append(f"Location: {job_data.location}")
    if job_data.description:
        job_info.append(f"Description: {job_data.description}")
    # Keywords are now handled separately, so we can remove them from here to avoid redundancy
    # if job_data.keywords:
    #     job_info.append(f"Key Skills/Keywords: {', '.join(job_data.keywords)}")
    
    return "\n".join(job_info)


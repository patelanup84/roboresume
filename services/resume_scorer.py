"""
Resume scoring service - handles ATS validation
"""

import os
import glob
from typing import Optional
from openai import OpenAI
from pypdf import PdfReader

# Local imports
from models import ATSValidationResult
from config import ATS_PROMPT_TEXT

def score_resume(session_path: str, client: OpenAI, model_name: str) -> str:
    """
    Finds the generated PDF, extracts its text, and runs an AI-powered ATS
    analysis against the original job posting.
    """
    print("\n=== Step 5: Validating Resume (ATS Score) ===")
    
    try:
        # 1. Find the generated PDF
        pdf_files = glob.glob(os.path.join(session_path, '*.pdf'))
        if not pdf_files:
            raise FileNotFoundError("Could not find the generated PDF in the session directory.")
        pdf_path = pdf_files[0]
        
        # 2. Extract text from the PDF
        reader = PdfReader(pdf_path)
        resume_text = ""
        for page in reader.pages:
            resume_text += page.extract_text() or ""
        
        if not resume_text.strip():
            raise ValueError("Extracted resume text is empty.")
            
        # 3. Read the original job posting markdown
        markdown_path = os.path.join(session_path, "job_posting.md")
        with open(markdown_path, "r", encoding="utf-8") as f:
            job_description_text = f.read()
            
        # 4. Run the AI analysis
        print("🤖 Running AI-powered ATS analysis...")
        response = client.chat.completions.create(
            model=model_name,
            response_model=ATSValidationResult,
            messages=[
                {
                    "role": "system",
                    "content": ATS_PROMPT_TEXT
                },
                {
                    "role": "user",
                    "content": f"Here is the job description:\n\n{job_description_text}\n\n---\n\nHere is the resume text:\n\n{resume_text}"
                }
            ],
            max_tokens=2048,
            temperature=0.1
        )
        
        # 5. Save the result
        output_path = os.path.join(session_path, "ats_validation.json")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.model_dump_json(indent=4))
        
        print(f"✅ ATS analysis complete. Results saved to: {output_path}")
        return output_path

    except Exception as e:
        error_msg = f"❌ Error during ATS validation: {str(e)}"
        print(error_msg)
        raise  # Re-raise the exception to be caught by the Flask route


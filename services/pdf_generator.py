"""
PDF generation service - handles final PDF assembly
UPDATED for Resume Builder architecture compatibility
"""

import os
import json
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML as WeasyHTML, CSS as WeasyCSS

# Local imports
from models import JobListing, TailoredResumeContent, IdealCandidateProfile


def generate_pdf(session_path: str, user_profile_path: str, pdf_config: dict) -> str:
    """
    Reads all intermediate files and generates the final PDF.
    UPDATED for Resume Builder architecture - now works with both new and legacy formats.
    """
    print("\n=== Step 4: Generating PDF ===")
    
    # Load the tailored resume content (this file name stays the same)
    tailored_content_path = os.path.join(session_path, "tailored_resume_content.json")
    with open(tailored_content_path, "r", encoding="utf-8") as f:
        tailored_content_data = json.load(f)
    
    # Load user profile for personal info
    with open(user_profile_path, "r", encoding="utf-8") as f:
        user_profile = json.load(f)
    
    # Try to load job data - prefer new format, fall back to legacy
    job_data = _load_job_analysis_data(session_path)
    
    # Generate final resume data
    final_resume_data = _assemble_final_resume_builder(user_profile, tailored_content_data, job_data, pdf_config)
    
    # Save final resume data
    final_resume_path = os.path.join(session_path, "final_resume_data.json")
    with open(final_resume_path, "w", encoding="utf-8") as f:
        json.dump(final_resume_data, f, indent=4)
    
    # Generate PDF
    pdf_output_path = _create_pdf_from_data(final_resume_data, session_path, pdf_config)
    
    print(f"📄 PDF generated successfully: {pdf_output_path}")
    return pdf_output_path


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _load_job_analysis_data(session_path: str) -> dict:
    """
    Loads job analysis data, preferring new format over legacy.
    """
    # Try new Resume Builder format first
    ideal_profile_path = os.path.join(session_path, "ideal_candidate_profile.json")
    if os.path.exists(ideal_profile_path):
        print("📊 Loading job analysis from ideal_candidate_profile.json (Resume Builder format)")
        with open(ideal_profile_path, "r", encoding="utf-8") as f:
            ideal_profile = json.load(f)
        
        # Convert to a format compatible with PDF generation
        return {
            "company_name": "Target Company",  # Default since new format doesn't store this
            "position_title": "Target Position",  # Default since new format doesn't store this
            "experience_summary": ideal_profile.get("experience_summary", ""),
            "top_technical_skills": ideal_profile.get("top_technical_skills", []),
            "top_soft_skills": ideal_profile.get("top_soft_skills", []),
            "format": "ideal_candidate_profile"
        }
    
    # Fall back to legacy format
    legacy_path = os.path.join(session_path, "structured_job_data.json")
    if os.path.exists(legacy_path):
        print("📊 Loading job analysis from structured_job_data.json (Legacy format)")
        with open(legacy_path, "r", encoding="utf-8") as f:
            legacy_data = json.load(f)
        legacy_data["format"] = "legacy"
        return legacy_data
    
    # If neither exists, return minimal data
    print("⚠️ No job analysis data found, using minimal defaults")
    return {
        "company_name": "Target Company",
        "position_title": "Target Position", 
        "format": "none"
    }


def _assemble_final_resume_builder(user_profile: dict, tailored_content: dict, job_data: dict, pdf_config: dict) -> dict:
    """
    Assembles the final resume data for the Resume Builder architecture.
    UPDATED to work with new data structure.
    """
    # Start with personal info from user profile
    final_resume = user_profile.get("personal_info", {}).copy()
    
    # Add the built content from Resume Builder
    final_resume.update({
        "summary": tailored_content.get("summary", ""),
        "work_experience": tailored_content.get("work_experience", []),
        "education": tailored_content.get("education", []),
        "skills": tailored_content.get("skills", []),
        "projects": tailored_content.get("projects", [])
    })
    
    # Add job targeting info
    final_resume["target_role"] = tailored_content.get("target_role", job_data.get("experience_summary", ""))
    
    # Add company name if available
    if job_data.get("company_name"):
        final_resume["target_company"] = job_data["company_name"]
    
    return final_resume


def _assemble_final_resume_legacy(base_resume: dict, tailored_content: TailoredResumeContent, job_data: JobListing, pdf_config: dict) -> dict:
    """
    Legacy function - assembles final resume for old tailoring architecture.
    KEPT for backward compatibility.
    """
    final_resume = base_resume.copy()
    
    # Update with tailored content
    if tailored_content.summary:
        final_resume["summary"] = tailored_content.summary
    
    if tailored_content.work_experience:
        final_resume["work_experience"] = [exp.model_dump() for exp in tailored_content.work_experience]
    
    if tailored_content.education:
        final_resume["education"] = [edu.model_dump() for edu in tailored_content.education]
    
    if tailored_content.skills:
        final_resume["skills"] = [skill.model_dump() for skill in tailored_content.skills]
    
    if tailored_content.projects:
        final_resume["projects"] = [proj.model_dump() for proj in tailored_content.projects]
    
    # Add job targeting info
    final_resume["target_role"] = tailored_content.target_role
    if job_data.company_name:
        final_resume["target_company"] = job_data.company_name
    
    return final_resume


def _create_pdf_from_data(resume_data: dict, session_path: str, pdf_config: dict) -> str:
    """
    Creates PDF from resume data using HTML template.
    UNCHANGED - works with both architectures.
    """
    try:
        # Setup Jinja2 environment
        template_dir = os.path.dirname(pdf_config["template_path"])
        template_name = os.path.basename(pdf_config["template_path"])
        
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template(template_name)
        
        # Render HTML
        html_content = template.render(resume=resume_data, pdf_config=pdf_config)
        
        # Save rendered HTML for debugging
        html_output_path = os.path.join(session_path, "rendered_resume.html")
        with open(html_output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Generate PDF
        pdf_output_path = os.path.join(session_path, "tailored_resume.pdf")
        
        html_doc = WeasyHTML(string=html_content, base_url=template_dir)
        css_doc = WeasyCSS(filename=pdf_config["css_path"])
        
        html_doc.write_pdf(pdf_output_path, stylesheets=[css_doc])
        
        print(f"✅ PDF created successfully: {pdf_output_path}")
        return pdf_output_path
        
    except Exception as e:
        error_msg = f"❌ Error creating PDF: {str(e)}"
        print(error_msg)
        raise ValueError(error_msg)



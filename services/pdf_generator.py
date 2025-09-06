"""
PDF generation service - handles final PDF assembly
EXTRACTED FROM jobbot resume_pipeline.py (step 4)
"""

import os
import json
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML as WeasyHTML, CSS as WeasyCSS

# Local imports
from models import JobListing, TailoredResumeContent


def generate_pdf(session_path: str, base_resume_path: str, pdf_config: dict) -> str:
    """
    Reads all intermediate files and generates the final PDF.
    EXTRACTED FROM jobbot resume_pipeline.py step_4_assemble_and_create_pdf
    """
    print("\n=== Step 4: Generating PDF ===")
    
    # Load all required data
    job_data_path = os.path.join(session_path, "structured_job_data.json")
    tailored_content_path = os.path.join(session_path, "tailored_resume_content.json")
    
    with open(job_data_path, "r", encoding="utf-8") as f:
        job_data = JobListing.model_validate_json(f.read())
    
    with open(tailored_content_path, "r", encoding="utf-8") as f:
        tailored_content = TailoredResumeContent.model_validate_json(f.read())
    
    with open(base_resume_path, "r", encoding="utf-8") as f:
        base_resume = json.load(f)
    
    # Generate final resume data
    final_resume_data = _assemble_final_resume(base_resume, tailored_content, job_data, pdf_config)
    
    # Save final resume data
    final_resume_path = os.path.join(session_path, "final_resume_data.json")
    with open(final_resume_path, "w", encoding="utf-8") as f:
        json.dump(final_resume_data, f, indent=4)
    
    # Generate PDF
    pdf_output_path = _create_pdf_from_data(final_resume_data, session_path, pdf_config)
    
    print(f"📄 PDF generated successfully: {pdf_output_path}")
    return pdf_output_path


# ============================================================================
# HELPER FUNCTIONS (EXTRACTED FROM jobbot resume_pipeline.py)
# ============================================================================

def _assemble_final_resume(base_resume: dict, tailored_content: TailoredResumeContent, job_data: JobListing, pdf_config: dict) -> dict:
    """
    Assembles the final resume data by merging base resume with tailored content.
    EXTRACTED FROM jobbot resume_pipeline.py
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
    EXTRACTED FROM jobbot resume_pipeline.py
    """
    try:
        # Setup Jinja2 environment
        template_dir = os.path.dirname(pdf_config["template_path"])
        template_name = os.path.basename(pdf_config["template_path"])
        
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template(template_name)
        
        # Render HTML
        html_content = template.render(resume=resume_data, pdf_config=pdf_config)  # FIXED LINE
        
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



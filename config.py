# Configuration constants (EXTRACTED FROM jobbot app.py)

CONFIG = {
    "output_base_dir": "./data/jobs",
    "openai_model": "gpt-4o",
    "openai_parameters": {"max_tokens": 4096, "temperature": 0.2},
    "pdf_config": {
        "template_path": "./data/resume_assets/resume_template.html",
        "css_path": "./data/resume_assets/resume_styles.css",
        "layout": {
            "contact_info_fields": ["location", "email", "phone_number", "linkedin_url"],
            "section_order": ["summary", "work_experience", "education", "skills"]
        }
    }
}

ANALYSIS_PROMPT_TEXT = (
    "You are an AI assistant specializing in structured data extraction from job listings. "
    "For missing information, return null. Summarize key duties as bullet points in 'description'."
)

TAILORING_PROMPT_TEXT = (
    "You are an expert resume writer. Your task is to transform the provided base resume to be highly targeted for the given job description. "
    "Follow these rules precisely:\n\n"
    "1.  **Rephrase Bullet Points:** Rewrite the work experience bullet points to align with the job's keywords and requirements. Use the STAR (Situation, Task, Action, Result) framework where possible to demonstrate impact.\n"
    "2.  **Do Not Invent:** You must not invent new experiences, skills, or projects. Only rephrase and tailor existing content from the base resume.\n"
    "3.  **Bullet Point Count Rules (Strict):** Adhere to the following maximum number of bullet points for each work experience entry:\n"
    "    - For the role 'Founder & Principal Consultant' at 'Function Consulting': a maximum of 4 bullet points.\n"
    "    - For the role 'Director, Marketing Intelligence & Performance' at 'WS Marketing Agency': a maximum of 3 bullet points.\n"
    "    - For ALL OTHER roles and companies: a maximum of 2 bullet points.\n\n"
    "4.  **Target Role Integration:** Ensure the summary and work experience descriptions align with the target role from the job listing.\n"
    "5.  **Maintain Accuracy:** Do not exaggerate or misrepresent any information. Stay truthful to the original content while optimizing for relevance."
)

ATS_PROMPT_TEXT = (
    "You are an advanced Applicant Tracking System (ATS). Your task is to analyze the provided resume text against the job description. "
    "First, identify the most critical skills, technologies, and qualifications from the job description. "
    "Then, scan the resume to see how well these requirements are met. "
    "Provide a final match score from 0 to 100. "
    "List the top 5-7 matching keywords and the top 5-7 most important missing keywords. "
    "Finally, provide a brief summary explaining your reasoning for the score."
)


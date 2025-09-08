# Configuration constants

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

# --------------------------------------------------------------------------
# Resume Builder Prompts
# --------------------------------------------------------------------------

JOB_ANALYSIS_PROMPT = (
    "You are an expert HR analyst. Analyze the provided job description and extract a profile of the ideal candidate. "
    "Focus on identifying the most critical skills and experiences required for success in this role. "
    "Your output must be a structured JSON object that conforms to the `IdealCandidateProfile` model."
)

WORK_EXPERIENCE_PROMPT = (
    "You are an expert resume writer building the 'Work Experience' section. Your task is to intelligently select and rewrite achievements from the user's comprehensive profile to create a highly targeted resume section.\n\n"
    "**Process:**\n"
    "1.  **Review the `IdealCandidateProfile`**: Understand the key technical and soft skills the employer is looking for.\n"
    "2.  **Scan the `UserProfile`**: Look through the user's entire work history.\n"
    "3.  **Select Achievements**: For each job, select the 2-3 achievements whose `tags` most closely align with the skills in the `IdealCandidateProfile`. Prioritize achievements with quantifiable results.\n"
    "4.  **Rewrite Selected Achievements**: Rewrite each selected achievement to be more impactful. Start with a strong action verb, use the STAR method, and subtly weave in keywords from the `IdealCandidateProfile`. Ensure each bullet is a dense, 2-line description (approx. 30-40 words).\n\n"
    "Your final output must be a JSON object containing only the `work_experience` list, conforming to the provided model."
)

SKILLS_PROMPT = (
    "You are a resume writer building the 'Skills' section. Your task is to select and organize the most relevant skills from the user's profile.\n\n"
    "**Process:**\n"
    "1.  **Review the `IdealCandidateProfile`**: Identify the top technical skills required for the job.\n"
    "2.  **Scan the `UserProfile`**: Look at all the skills the user possesses.\n"
    "3.  **Select & Organize**: Create a `skills` section that prioritizes the skills listed in the `IdealCandidateProfile`. Group them into logical categories.\n\n"
    "Your output must be a JSON object containing the `skills` list."
)

SUMMARY_PROMPT = (
    "You are a resume writer crafting a professional summary. Your task is to synthesize the *already built* work experience and skills sections into a powerful, concise summary.\n\n"
    "**Process:**\n"
    "1.  **Review the `IdealCandidateProfile`**: Understand the core requirements of the role.\n"
    "2.  **Review the `BuiltResumeSections`**: Analyze the most important achievements and skills that were selected for the resume.\n"
    "3.  **Write Summary**: Craft a 2-3 sentence summary that highlights the candidate's strongest qualifications as reflected in the built sections, mirroring the language of the job description.\n\n"
    "Your output must be a JSON object containing only the `summary` string."
)

# --------------------------------------------------------------------------
# Legacy Prompts (Keep for now, may be used in job analysis step)
# --------------------------------------------------------------------------

ANALYSIS_PROMPT_TEXT = (
    "You are an AI assistant specializing in structured data extraction from job listings. "
    "For missing information, return null. Summarize key duties as bullet points in 'description'."
)

ATS_PROMPT_TEXT = (
    "You are an advanced Applicant Tracking System (ATS). Your task is to analyze the provided resume text against the job description. "
    "First, identify the most critical skills, technologies, and qualifications from the job description. "
    "Then, scan the resume to see how well these requirements are met. "
    "Provide a final match score from 0 to 100. "
    "List the top 5-7 matching keywords and the top 5-7 most important missing keywords. "
    "Finally, provide a brief summary explaining your reasoning for the score."
)

import os
import sys
import json
import shutil
from datetime import datetime
import instructor
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional

# ============================================================================
# Path Setup - path to look three directories up to the project root ---
# ============================================================================
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ============================================================================

from utils import ensure_directory_exists
from services.pdf_generator import generate_pdf
from config import CONFIG

# --- SETUP ---
load_dotenv()
client = instructor.patch(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

# ============================================================================
# 1. DATA MODELS FOR THE BUILDER PIPELINE
# ============================================================================

class IdealCandidateProfile(BaseModel):
    """Defines the key traits and skills extracted from a job description."""
    top_technical_skills: List[str] = Field(..., description="A list of the 5-7 most critical technical skills or technologies.")
    top_soft_skills: List[str] = Field(..., description="A list of the 3-4 most important soft skills or professional traits (e.g., leadership, problem-solving).")
    experience_summary: str = Field(..., description="A 1-2 sentence summary of the ideal candidate's required experience.")

class GeneratedWorkExperience(BaseModel):
    company: str
    position: str
    date: str
    description: List[str]

class GeneratedSkill(BaseModel):
    category: str
    entries: List[str]

class GeneratedResume(BaseModel):
    """The final, assembled resume content, ready for PDF generation."""
    summary: str
    work_experience: List[GeneratedWorkExperience]
    skills: List[GeneratedSkill]
    # We will add other sections like education directly from the user profile.

# ============================================================================
# 2. PROMPTS FOR EACH STEP OF THE BUILDER PIPELINE
# ============================================================================

JOB_ANALYSIS_PROMPT = (
    "You are an expert HR analyst. Analyze the provided job description and extract a profile of the ideal candidate. "
    "Focus on identifying the most critical skills and experiences required for success in this role. "
    "Your output must be a structured JSON object that conforms to the `IdealCandidateProfile` model."
)

WORK_EXPERIENCE_PROMPT = (
    "You are an expert resume writer building the 'Work Experience' section. Your task is to intelligently select and rewrite achievements from the user's comprehensive profile to create a highly targeted resume section.\n\n"
    "**Process:**\n"
    "1.  **Review the `IdealCandidateProfile`**: Understand the key technical and soft skills the employer is looking for.\n"
    "2.  **Scan the `UserProfile`**: Look through the user's entire work history provided in the `work_experience` section.\n"
    "3.  **Select Achievements**: For each job listed in the user's profile, select the 2-3 achievements whose `tags` most closely align with the skills in the `IdealCandidateProfile`. Prioritize achievements with quantifiable results.\n"
    "4.  **Rewrite Selected Achievements**: Rewrite each selected achievement to be impactful. Start with a strong action verb, use the STAR method, and subtly weave in keywords from the `IdealCandidateProfile`. Ensure each bullet is a dense, 2-line description (approx. 30-40 words).\n\n"
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

# ============================================================================
# 3. SCRIPT CONFIGURATION
# ============================================================================

INPUT_JOB_POSTING_FILE = "sample_job_post_consulting.md"
INPUT_USER_PROFILE_FILE = "user_profile.json"
OUTPUT_DIRECTORY = "/output"
MODEL_NAME = "gpt-4o"
API_PARAMETERS = {"temperature": 0.2}

# ============================================================================
# 4. BUILDER PIPELINE FUNCTIONS
# ============================================================================

def step_1_analyze_job(job_description: str) -> IdealCandidateProfile:
    """Analyzes the job description to create an ideal candidate profile."""
    print("  Running Step 1: Analyzing Job Description...")
    profile = client.chat.completions.create(
        model=MODEL_NAME,
        response_model=IdealCandidateProfile,
        messages=[
            {"role": "system", "content": JOB_ANALYSIS_PROMPT},
            {"role": "user", "content": job_description}
        ],
        **API_PARAMETERS
    )
    print("  ✅ Analysis Complete.")
    return profile

def step_2_build_work_experience(profile: dict, analysis: IdealCandidateProfile, job_desc: str) -> List[GeneratedWorkExperience]:
    """Selects and rewrites work experience from the user profile."""
    print("  Running Step 2: Building Work Experience Section...")
    
    user_prompt = (
        f"**Ideal Candidate Profile:**\n{analysis.model_dump_json(indent=2)}\n\n"
        f"**User's Full Profile (for context):**\n{json.dumps(profile, indent=2)}\n\n"
        f"**Original Job Description (for keyword alignment):**\n{job_desc}"
    )
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        response_model=GeneratedResume,
        messages=[
            {"role": "system", "content": WORK_EXPERIENCE_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        **API_PARAMETERS
    )
    print("  ✅ Work Experience Built.")
    return response.work_experience

def step_3_build_skills(profile: dict, analysis: IdealCandidateProfile) -> List[GeneratedSkill]:
    """Builds the skills section."""
    print("  Running Step 3: Building Skills Section...")
    user_prompt = (
        f"**Ideal Candidate Profile:**\n{analysis.model_dump_json(indent=2)}\n\n"
        f"**User's Full Profile (for context):**\n{json.dumps(profile, indent=2)}"
    )
    response = client.chat.completions.create(
        model=MODEL_NAME,
        response_model=GeneratedResume,
        messages=[
            {"role": "system", "content": SKILLS_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        **API_PARAMETERS
    )
    print("  ✅ Skills Section Built.")
    return response.skills

def step_4_build_summary(built_experience: List[GeneratedWorkExperience], built_skills: List[GeneratedSkill], analysis: IdealCandidateProfile) -> str:
    """Writes the summary based on the already-built sections."""
    print("  Running Step 4: Writing Summary...")
    
    built_sections = {
        "work_experience": [job.model_dump() for job in built_experience],
        "skills": [skill.model_dump() for skill in built_skills]
    }
    
    user_prompt = (
        f"**Ideal Candidate Profile:**\n{analysis.model_dump_json(indent=2)}\n\n"
        f"**Built Resume Sections (for synthesis):**\n{json.dumps(built_sections, indent=2)}"
    )
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        response_model=GeneratedResume,
        messages=[
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        **API_PARAMETERS
    )
    print("  ✅ Summary Written.")
    return response.summary

def run_pipeline():
    """Main function to orchestrate the resume builder pipeline."""
    print("--- Starting Resume Builder Pipeline Test ---")
    ensure_directory_exists(OUTPUT_DIRECTORY)
    
    # --- Load Inputs ---
    try:
        with open(INPUT_JOB_POSTING_FILE, "r") as f:
            job_description = f.read()
        with open(INPUT_USER_PROFILE_FILE, "r") as f:
            user_profile = json.load(f)
    except FileNotFoundError as e:
        print(f"❌ ERROR: Input file not found. {e}")
        return

    # --- Execute Pipeline ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Step 1
    analysis_profile = step_1_analyze_job(job_description)
    analysis_output_path = os.path.join(OUTPUT_DIRECTORY, f"builder_run_{timestamp}_analysis.json")
    with open(analysis_output_path, "w") as f:
        f.write(analysis_profile.model_dump_json(indent=4))
    print(f"  📄 Analysis saved to: {analysis_output_path}")

    # Step 2
    built_work_experience = step_2_build_work_experience(user_profile, analysis_profile, job_description)

    # Step 3
    built_skills = step_3_build_skills(user_profile, analysis_profile)
    
    # Step 4
    built_summary = step_4_build_summary(built_work_experience, built_skills, analysis_profile)
    
    # --- Assemble Final Resume ---
    print("\n  Assembling Final Resume...")
    final_resume_content = {
        "summary": built_summary,
        "work_experience": [job.model_dump() for job in built_work_experience],
        "education": user_profile.get("education", []),
        "skills": [skill.model_dump() for skill in built_skills],
        "target_role": analysis_profile.experience_summary
    }
    
    final_resume_path = os.path.join(OUTPUT_DIRECTORY, f"builder_run_{timestamp}_final_resume.json")
    with open(final_resume_path, "w") as f:
        json.dump(final_resume_content, f, indent=4)
    print(f"  ✅ Final resume content assembled and saved to: {final_resume_path}")

    # --- Generate PDF ---
    print("\n  Generating PDF...")
    temp_session_dir = os.path.join(OUTPUT_DIRECTORY, f"temp_session_{timestamp}")
    os.makedirs(temp_session_dir, exist_ok=True)
    try:
        with open(os.path.join(temp_session_dir, "tailored_resume_content.json"), "w") as f:
            json.dump(final_resume_content, f, indent=4)
            
        temp_base_resume = user_profile.get("personal_info", {})
        temp_base_resume_path = os.path.join(temp_session_dir, "base_resume.json")
        with open(temp_base_resume_path, "w") as f:
            json.dump(temp_base_resume, f, indent=4)
        
        with open(os.path.join(temp_session_dir, "structured_job_data.json"), "w") as f:
             json.dump({"company_name": "Target Company"}, f, indent=4) # Using a placeholder

        pdf_path_in_session = generate_pdf(
            session_path=temp_session_dir,
            base_resume_path=temp_base_resume_path,
            pdf_config=CONFIG["pdf_config"]
        )
        final_pdf_path = os.path.join(OUTPUT_DIRECTORY, f"builder_run_{timestamp}_final.pdf")
        shutil.copy(pdf_path_in_session, final_pdf_path)
        print(f"  ✅ PDF generated and saved to: {final_pdf_path}")
    finally:
        if os.path.exists(temp_session_dir):
            shutil.rmtree(temp_session_dir)
            
    print("\n--- Resume Builder Pipeline Test Complete ---")

if __name__ == "__main__":
    run_pipeline()
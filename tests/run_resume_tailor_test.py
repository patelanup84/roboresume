import os
import sys
import instructor
import shutil
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# --- IMPORTS FROM YOUR PROJECT ---

# This block adds the project's root directory to Python's search path.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from services.resume_tailor import tailor_resume
from utils import ensure_directory_exists

# --- SETUP ---
load_dotenv()
client = instructor.patch(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

# ============================================================================
# SCRIPT CONFIGURATION
#
# Edit the variables below to configure your test run.
# ============================================================================

# 1. Specify the input files from your test_data folder.
#    NOTE: The analysis file is the *output* from a job_analyzer run.
#    Copy an output file from 'tests/test_output' into 'tests/test_data' to use it here.
INPUT_ANALYSIS_FILE = "tests/test_data/v2/sample_job_analysis.json" 
INPUT_BASE_RESUME_FILE = "data/resume_assets/base_resume.json" # Using the default base resume

# 2. Specify the AI model, parameters, and prompt.
MODEL_NAME = "gpt-4o"
API_PARAMETERS = {"max_tokens": 4096, "temperature": 0.2}
KEYWORDS_TO_INJECT = [
    "Python", "Flask", "Backend APIs", "AWS", "Docker", "CI/CD", "Scalability"
] # These are extracted from the job analysis and can be tweaked here.

# TAILORING_PROMPT_TEXT = (
#     "You are an expert resume writer. Your task is to transform the provided base resume to be highly targeted for the given job description. "
#     "Follow these rules precisely:\n\n"
#     "1.  **Rephrase Bullet Points:** Rewrite the work experience bullet points to align with the job's keywords and requirements. Use the STAR (Situation, Task, Action, Result) framework where possible to demonstrate impact.\n"
#     "2.  **Do Not Invent:** You must not invent new experiences, skills, or projects. Only rephrase and tailor existing content from the base resume.\n"
#     "3.  **Bullet Point Count Rules (Strict):** Adhere to the following maximum number of bullet points for each work experience entry:\n"
#     "    - For the role 'Founder & Principal Consultant' at 'Function Consulting': a maximum of 4 bullet points.\n"
#     "    - For the role 'Director, Marketing Intelligence & Performance' at 'WS Marketing Agency': a maximum of 3 bullet points.\n"
#     "    - For ALL OTHER roles and companies: a maximum of 2 bullet points.\n\n"
#     "4.  **Target Role Integration:** Ensure the summary and work experience descriptions align with the target role from the job listing.\n"
#     "5.  **Maintain Accuracy:** Do not exaggerate or misrepresent any information. Stay truthful to the original content while optimizing for relevance."
# )

# Replace the old TAILORING_PROMPT_TEXT with this new one

TAILORING_PROMPT_TEXT = (
    "You are an expert ATS-optimized resume writer and career strategist, specializing in creating highly targeted technical resumes. "
    "Your mission is to meticulously transform the provided base resume. You will rewrite the summary and work experience bullet points to be "
    "exceptionally aligned with the target job description, ensuring the final content is impactful, metric-driven, and optimized for both "
    "ATS and human reviewers.\n\n"
    
    "Follow this two-step process and adhere to all rules precisely:\n\n"
    
    "**Step 1: Deep Analysis**\n"
    "First, deeply analyze the `Job Description`. Identify the most critical keywords, required skills (both technical and soft), and core responsibilities. "
    "Pay close attention to the company's language and tone.\n\n"
    
    "**Step 2: Strategic Content Rewriting**\n" 
    "Next, rewrite the `summary` and `work_experience` bullet points from the `Base Resume`. Your goal is not just to insert keywords, but to reframe the "
    "candidate's existing experience to tell a compelling story that directly addresses the job's needs.\n\n"
    
    "---\n"
    "**CRITICAL RULES FOR REWRITING**\n\n"
    
    "1. **The STAR Method for Technical Impact:**\n"
    "   Every rewritten bullet point must follow the STAR (Situation, Task, Action, Result) framework to demonstrate clear impact.\n"
    "   For example: `**Engineered** (Action) a real-time data processing pipeline (Task) using **Python** and **Kafka** (Tools), resulting in a **30%** reduction in data latency (Result).`\n\n"
    
    "2. **Quantify Everything Possible:**\n"
    "   Incorporate quantifiable metrics (e.g., percentages, dollar amounts, user numbers, project scale, time saved) to substantiate achievements.\n"
    "   If a number doesn't exist in the base resume, frame the result in terms of business impact or efficiency gained.\n\n"
    
    "3. **Strategic Keyword Integration & Bolding:**\n"
    "   Seamlessly weave the critical keywords you identified in Step 1 into the rewritten content.\n"
    "   You MUST **bold** important keywords, technologies, and metrics using Markdown (`**keyword**`) to make them stand out to reviewers.\n\n"
    
    "4. **Adhere to Strict Bullet Point Counts (Strict):**\n"
    "   - For the role 'Founder & Principal Consultant' at 'Function Consulting': a maximum of 4 bullet points.\n"
    "   - For the role 'Director, Marketing Intelligence & Performance' at 'WS Marketing Agency': a maximum of 3 bullet points.\n"
    "   - For ALL OTHER roles and companies: a maximum of 2 bullet points.\n\n"
    
    "5. **CRITICAL: Do Not Invent or Exaggerate:**\n"
    "   You must **never** invent new skills, experiences, or metrics. Your task is to rephrase and reframe existing content truthfully."
)

# 3. Define where the results will be saved.
OUTPUT_DIRECTORY = "tests/test_output"

# ============================================================================

def run_test():
    """
    Main function to run the resume tailoring test.
    """
    print("--- Starting Resume Tailor Test ---")

    if not os.path.exists(INPUT_ANALYSIS_FILE):
        print(f"❌ ERROR: Input file not found: '{INPUT_ANALYSIS_FILE}'")
        print("Please run the job analyzer test first, then copy its output JSON into 'tests/test_data/' and rename it to 'sample_job_analysis.json'.")
        return

    # --- 1. Preparation ---
    ensure_directory_exists(OUTPUT_DIRECTORY)
    temp_session_dir = f"temp_session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    os.makedirs(temp_session_dir, exist_ok=True)
    
    # The service expects specific filenames inside the session directory
    shutil.copy(INPUT_ANALYSIS_FILE, os.path.join(temp_session_dir, "structured_job_data.json"))
    shutil.copy(INPUT_BASE_RESUME_FILE, os.path.join(temp_session_dir, "base_resume.json"))
    
    # Path for the service to use for the base resume
    base_resume_path_in_session = os.path.join(temp_session_dir, "base_resume.json")

    print(f"Input analysis: '{INPUT_ANALYSIS_FILE}'")
    print(f"Input resume: '{INPUT_BASE_RESUME_FILE}'")
    print(f"Using model: '{MODEL_NAME}'")

    try:
        # --- 2. Execute the Service ---
        print("\nRunning live API call to OpenAI for resume tailoring...")
        
        # Temporarily override the prompt in the config for this test
        from config import TAILORING_PROMPT_TEXT as ORIGINAL_PROMPT
        import config
        config.TAILORING_PROMPT_TEXT = TAILORING_PROMPT_TEXT

        output_json_path = tailor_resume(
            session_path=temp_session_dir,
            base_resume_path=base_resume_path_in_session,
            client=client,
            model_name=MODEL_NAME,
            api_parameters=API_PARAMETERS,
            keywords=KEYWORDS_TO_INJECT
        )

        # Restore original prompt
        config.TAILORING_PROMPT_TEXT = ORIGINAL_PROMPT

        print("✅ Tailoring complete.")

        # --- 3. Save the Output ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_output_filename = f"resume_tailor_run_{timestamp}.json"
        final_output_path = os.path.join(OUTPUT_DIRECTORY, final_output_filename)

        shutil.copy(output_json_path, final_output_path)
        
        print(f"\n✅ Test finished successfully!")
        print(f"📄 Output saved to: {final_output_path}")

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
    finally:
        # --- 4. Cleanup ---
        if os.path.exists(temp_session_dir):
            shutil.rmtree(temp_session_dir)
        print("--- Test Complete ---")


if __name__ == "__main__":
    run_test()
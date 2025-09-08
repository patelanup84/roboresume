import os
import sys
import json
import shutil
from datetime import datetime
import instructor
from openai import OpenAI
from dotenv import load_dotenv

# ============================================================================
# Path Setup
# ============================================================================
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
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
# SCRIPT CONFIGURATION
# ============================================================================

# 1. Specify the input files for the test.
INPUT_JOB_POSTING_FILE = "tests/test_data/v3/sample_job_post_consulting.md"
INPUT_BASE_RESUME_DATA_FILE = "tests/test_data/v3/base_resume_data.json"
INPUT_INSTRUCTIONAL_TEMPLATE_FILE = "tests/test_data/v3/consulting_instructional_template_v4.json"
INPUT_MOCK_JOB_ANALYSIS_FILE = "tests/test_data/v3/mock_job_analysis.json"

# 2. Define where the results will be saved.
OUTPUT_DIRECTORY = "tests/test_output"

# 3. Specify the AI model and parameters.
MODEL_NAME = "gpt-4o"
API_PARAMETERS = {"max_tokens": 4096, "temperature": 0.25}

# 4. This is the "Meta-Prompt" that instructs the AI on HOW to perform the task.
META_PROMPT_TEXT = (
    "You are a sophisticated AI resume generation engine. "
    "Your task is to populate a given JSON `Instructional Template`. This template contains fields where the value is an "
    "`{Instruction: ...}` string. You must follow these instructions precisely to generate the content for each field.\n\n"
    "You will be provided with two sources of information:\n"
    "1. A `Job Description` to align the tone, keywords, and focus of the generated content.\n"

    "2. The user's `Base Resume Data`, which serves as the absolute source of truth for their experience, skills, and facts. "
    "You must use this data to inform your writing.\n\n"
    "**CRITICAL RULES:**\n"
    "- Replace EVERY `{Instruction: ...}` string with your newly generated content.\n"
    "- Your final output MUST be a valid JSON object with the exact same structure as the `Instructional Template`.\n"
    "- Do NOT include the instructions themselves (e.g., `{Instruction: ...}`) in your final output.\n"
    "- Use the `Base Resume Data` as the factual basis for your writing. You must not invent or hallucinate facts, skills, or experiences not present in this data.\n"
    "- Adhere to all constraints mentioned in the instructions, such as length, format (e.g., 'Accomplished [X]...'), or traits to emphasize."
)
# ============================================================================

def transform_for_pdf(generated_json: dict, mock_job_analysis: dict) -> dict:
    """
    Transforms the JSON from the instructional template to match the Pydantic
    model expected by the pdf_generator service.
    """
    transformed = generated_json.copy()

    # 1. Add the required 'target_role'
    transformed['target_role'] = mock_job_analysis.get('position_title', 'Consulting Associate')

    # 2. **FIX:** Smartly extract the generated text from the 'description' objects.
    if 'work_experience' in transformed and isinstance(transformed['work_experience'], list):
        for job in transformed['work_experience']:
            if 'description' in job and isinstance(job['description'], list):
                new_description_list = []
                for item in job['description']:
                    # The AI may return a simple string OR the object with the filled-in instruction.
                    # This handles both cases gracefully.
                    if isinstance(item, dict) and 'instruction' in item:
                        new_description_list.append(item['instruction'])
                    elif isinstance(item, str):
                        new_description_list.append(item)
                job['description'] = new_description_list
                
    # Also handle extracurriculars which has the same structure
    if 'extracurricular_achievements' in transformed and isinstance(transformed['extracurricular_achievements'], list):
        for achievement in transformed['extracurricular_achievements']:
             if 'description' in achievement and isinstance(achievement['description'], list):
                new_description_list = []
                for item in achievement['description']:
                    if isinstance(item, str):
                         new_description_list.append(item)
                achievement['description'] = new_description_list


    # 3. Transform the 'skills' object into a list of objects
    if 'skills' in transformed and isinstance(transformed['skills'], dict):
        skills_list = []
        for category, entries_str in transformed['skills'].items():
            if category != "_comment" and isinstance(entries_str, str):
                # Split entries by comma, but also handle semicolons as a fallback
                entries = [e.strip() for e in entries_str.replace(';', ',').split(',')]
                skills_list.append({
                    "category": category.replace('_', ' ').title(),
                    "entries": entries
                })
        transformed['skills'] = skills_list

    return transformed


def run_test():
    """
    Main function to run the instructional template test and generate a PDF.
    """
    print("--- Starting Instructional Template Test ---")
    ensure_directory_exists(OUTPUT_DIRECTORY)
    temp_session_dir = os.path.join(OUTPUT_DIRECTORY, f"temp_session_{datetime.now().strftime('%Y%m%d%H%M%S')}")
    os.makedirs(temp_session_dir, exist_ok=True)

    try:
        # --- 1. Load All Input Files ---
        print(f"Loading job posting from: '{INPUT_JOB_POSTING_FILE}'")
        with open(INPUT_JOB_POSTING_FILE, "r", encoding="utf-8") as f:
            job_description = f.read()

        print(f"Loading base resume data from: '{INPUT_BASE_RESUME_DATA_FILE}'")
        with open(INPUT_BASE_RESUME_DATA_FILE, "r", encoding="utf-8") as f:
            base_resume_data_str = f.read()

        print(f"Loading instructional template from: '{INPUT_INSTRUCTIONAL_TEMPLATE_FILE}'")
        with open(INPUT_INSTRUCTIONAL_TEMPLATE_FILE, "r", encoding="utf-8") as f:
            instructional_template_str = f.read()
            
        with open(INPUT_MOCK_JOB_ANALYSIS_FILE, "r", encoding="utf-8") as f:
            mock_job_analysis = json.load(f)

    except FileNotFoundError as e:
        print(f"❌ ERROR: Input file not found. {e}")
        return

    # --- 2. Construct the AI Prompt ---
    final_user_prompt = (
        "Here is the contextual information you need to complete your task:\n\n"
        "--- JOB DESCRIPTION ---\n"
        f"{job_description}\n\n"
        "--- BASE RESUME DATA (SOURCE OF TRUTH) ---\n"
        f"{base_resume_data_str}\n\n"
        "--- INSTRUCTIONAL TEMPLATE (FILL THIS OUT) ---\n"
        f"{instructional_template_str}"
    )

    # --- 3. Execute AI Generation ---
    print(f"\nRunning live API call to '{MODEL_NAME}'...")
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": META_PROMPT_TEXT},
            {"role": "user", "content": final_user_prompt},
        ],
        response_format={"type": "json_object"},
        **API_PARAMETERS
    )
    generated_content_str = response.choices[0].message.content
    print("✅ AI generation complete.")

    # --- 4. Save the AI-Generated JSON Output ---
    try:
        parsed_json = json.loads(generated_content_str)
    except json.JSONDecodeError:
        print("❌ ERROR: The AI returned invalid JSON. Saving the raw text for debugging.")
        parsed_json = {"error": "Invalid JSON from AI", "raw_response": generated_content_str}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_output_filename = f"instructional_run_raw_{timestamp}.json"
    json_output_path = os.path.join(OUTPUT_DIRECTORY, json_output_filename)
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=4)
    print(f"📄 Raw AI-generated JSON saved to: {json_output_path}")

    # --- 5. Generate the PDF ---
    print("\nStarting PDF generation...")
    try:
        # 5a. Transform the new JSON to the old format required by the PDF generator
        pdf_compatible_json = transform_for_pdf(parsed_json, mock_job_analysis)
        
        # 5b. Save the transformed JSON for debugging
        pdf_json_filename = f"instructional_run_for_pdf_{timestamp}.json"
        pdf_json_path = os.path.join(OUTPUT_DIRECTORY, pdf_json_filename)
        with open(pdf_json_path, "w", encoding="utf-8") as f:
            json.dump(pdf_compatible_json, f, indent=4)
        print(f"📄 Transformed JSON for PDF saved to: {pdf_json_path}")
        
        # 5c. Save the transformed JSON as the tailored content file in the temp directory.
        with open(os.path.join(temp_session_dir, "tailored_resume_content.json"), "w", encoding="utf-8") as f:
            json.dump(pdf_compatible_json, f, indent=4)
            
        # 5d. Copy other necessary files into the temp folder.
        shutil.copy(INPUT_BASE_RESUME_DATA_FILE, os.path.join(temp_session_dir, "base_resume.json"))
        shutil.copy(INPUT_MOCK_JOB_ANALYSIS_FILE, os.path.join(temp_session_dir, "structured_job_data.json"))
        
        base_resume_path_in_session = os.path.join(temp_session_dir, "base_resume.json")
        
        # 5e. Call the PDF generation service.
        pdf_path_in_session = generate_pdf(
            session_path=temp_session_dir,
            base_resume_path=base_resume_path_in_session,
            pdf_config=CONFIG["pdf_config"]
        )
        
        # 5f. Copy the final PDF to our main output folder.
        pdf_output_filename = f"instructional_run_{timestamp}.pdf"
        final_pdf_path = os.path.join(OUTPUT_DIRECTORY, pdf_output_filename)
        shutil.copy(pdf_path_in_session, final_pdf_path)
        
        print("✅ PDF generation complete.")
        print(f"📄 Generated PDF saved to: {final_pdf_path}")

    except Exception as e:
        print(f"\n❌ An error occurred during PDF generation: {e}")

    finally:
        # --- 6. Cleanup ---
        if os.path.exists(temp_session_dir):
            shutil.rmtree(temp_session_dir)
        print("\n--- Test Complete ---")


if __name__ == "__main__":
    run_test()
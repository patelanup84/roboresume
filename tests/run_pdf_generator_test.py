import os
import shutil
from datetime import datetime
import sys

# --- IMPORTS FROM YOUR PROJECT ---

# This block adds the project's root directory to Python's search path.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
from services.pdf_generator import generate_pdf
from utils import ensure_directory_exists
from config import CONFIG

# ============================================================================
# SCRIPT CONFIGURATION
#
# Edit the variables below to configure your test run.
# ============================================================================

# 1. Specify the necessary input files.
INPUT_TAILORED_RESUME_FILE = "tests/test_data/sample_tailored_resume.json"
INPUT_JOB_ANALYSIS_FILE = "tests/test_data/sample_job_analysis.json"
INPUT_BASE_RESUME_FILE = "data/resume_assets/base_resume.json"

# 2. Define where the final PDF will be saved.
OUTPUT_DIRECTORY = "tests/test_output"

# ============================================================================

def run_test():
    """
    Main function to run the PDF generation test.
    """
    print("--- Starting PDF Generator Test ---")

    # --- 1. Input Validation ---
    required_files = [INPUT_TAILORED_RESUME_FILE, INPUT_JOB_ANALYSIS_FILE, INPUT_BASE_RESUME_FILE]
    for f in required_files:
        if not os.path.exists(f):
            print(f"❌ ERROR: Required input file not found: '{f}'")
            print("Please ensure you have run the previous test scripts and copied the outputs to 'tests/test_data/'.")
            return

    # --- 2. Preparation ---
    ensure_directory_exists(OUTPUT_DIRECTORY)

    # Create a temporary session directory for the service to use
    temp_session_dir = f"temp_session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    os.makedirs(temp_session_dir, exist_ok=True)
    
    # The service expects specific filenames inside the session directory, so we copy and rename
    shutil.copy(INPUT_TAILORED_RESUME_FILE, os.path.join(temp_session_dir, "tailored_resume_content.json"))
    shutil.copy(INPUT_JOB_ANALYSIS_FILE, os.path.join(temp_session_dir, "structured_job_data.json"))
    shutil.copy(INPUT_BASE_RESUME_FILE, os.path.join(temp_session_dir, "base_resume.json"))
    
    base_resume_path_in_session = os.path.join(temp_session_dir, "base_resume.json")

    print(f"Using tailored content: '{INPUT_TAILORED_RESUME_FILE}'")
    print(f"Using base resume: '{INPUT_BASE_RESUME_FILE}'")
    print(f"Using job analysis: '{INPUT_JOB_ANALYSIS_FILE}'")

    try:
        # --- 3. Execute the Service ---
        print("\nGenerating PDF using application logic...")

        # This function reads the files from the session dir and creates the PDF inside it
        generated_pdf_path_in_session = generate_pdf(
            session_path=temp_session_dir,
            base_resume_path=base_resume_path_in_session,
            pdf_config=CONFIG["pdf_config"]
        )

        print("✅ PDF generation logic complete.")

        # --- 4. Save the Output ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_output_filename = f"generated_resume_{timestamp}.pdf"
        final_output_path = os.path.join(OUTPUT_DIRECTORY, final_output_filename)

        # Copy the final PDF from the temp session to our permanent output directory
        shutil.copy(generated_pdf_path_in_session, final_output_path)
        
        print(f"\n✅ Test finished successfully!")
        print(f"📄 PDF output saved to: {final_output_path}")

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
    finally:
        # --- 5. Cleanup ---
        # Remove the temporary session directory
        if os.path.exists(temp_session_dir):
            shutil.rmtree(temp_session_dir)
        print("--- Test Complete ---")


if __name__ == "__main__":
    run_test()
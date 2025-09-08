import os
import instructor
import asyncio
import json
import glob
import shutil
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from openai import OpenAI
from dotenv import load_dotenv
import zipfile
from werkzeug.utils import secure_filename

# --- IMPORTS FROM OUR FILES ---
from models import IdealCandidateProfile, ATSValidationResult
from config import CONFIG, JOB_ANALYSIS_PROMPT, WORK_EXPERIENCE_PROMPT, SKILLS_PROMPT, SUMMARY_PROMPT, ATS_PROMPT_TEXT
from utils import create_session_directory, cleanup_old_sessions, transform_workopolis_url
from utils import create_session_directory, cleanup_old_sessions, transform_workopolis_url, create_session_zip

# Import services
from services.job_analyzer import fetch_job_content, analyze_job_posting
from services.resume_tailor import tailor_resume
from services.pdf_generator import generate_pdf
from services.resume_scorer import score_resume


# --- APPLICATION SETUP ---
load_dotenv()
client = instructor.patch(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
app = Flask(__name__)
app.secret_key = os.urandom(24) 

# --- FLASK ROUTES ---
@app.route('/')
def home():
    """Displays the main form for inputting job details and uploading a resume."""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    """Handles form submission, starts the job analysis pipeline."""
    job_url = request.form.get('job_url', '').strip()
    job_description = request.form.get('job_description', '').strip()
    
    # --- Transform Workopolis URL if necessary ---
    if job_url:
        job_url = transform_workopolis_url(job_url)

    if not (job_url or job_description):
        flash("Error: Please provide either a job URL or job description.")
        return redirect(url_for('home'))
    
    # This route no longer handles resumes. It only sets up the session.
    session_id = create_session_directory(CONFIG["output_base_dir"], "job", "analysis")
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    
    if not session_path:
        flash("Error: Could not create session directory.")
        return redirect(url_for('home'))
    
    if job_url:
        source_config = {"type": "url", "url": job_url}
    elif job_description:
        source_config = {"type": "string", "text": job_description}
    else:
        # This case is already handled, but for safety
        flash("Error: No job URL or description provided.")
        return redirect(url_for('home'))
    
    try:
        asyncio.run(fetch_job_content(source_config, session_path))
        return redirect(url_for('review_joblisting', session_id=session_id))
    except Exception as e:
        flash(f"An error occurred during content scraping: {e}")
        return redirect(url_for('home'))

@app.route('/upload/bundle', methods=['POST'])
def upload_bundle():
    """Handles the upload of a session bundle (.zip) to resume a session."""
    if 'session_bundle' not in request.files:
        flash("Error: No file part in the request.")
        return redirect(url_for('home'))
    
    file = request.files['session_bundle']
    if file.filename == '':
        flash("Error: No file selected.")
        return redirect(url_for('home'))

    if file and file.filename.endswith('.zip'):
        # 1. Create a new session to extract the bundle into
        session_id = create_session_directory(CONFIG["output_base_dir"], "resumed", "session")
        session_path = os.path.join(CONFIG["output_base_dir"], session_id)
        
        try:
            # 2. Extract the zip file
            with zipfile.ZipFile(file, 'r') as zip_ref:
                zip_ref.extractall(session_path)
            
            # 3. Determine which step to redirect to (Updated for Resume Builder)
            extracted_files = os.listdir(session_path)
            if 'tailored_resume_content.json' in extracted_files:
                flash("✅ Session resumed at 'Review Built Resume' step.")
                return redirect(url_for('review_tailoring', session_id=session_id))
            elif 'ideal_candidate_profile.json' in extracted_files:
                flash("✅ Session resumed at 'Resume Builder' step.")
                return redirect(url_for('review_jobanalysis', session_id=session_id))
            elif 'structured_job_data.json' in extracted_files:  # Legacy support
                flash("✅ Session resumed at 'Job Analysis' step (Legacy).")
                return redirect(url_for('review_jobanalysis', session_id=session_id))
            elif 'job_posting.md' in extracted_files:
                flash("✅ Session resumed at 'Review Job Listing' step.")
                return redirect(url_for('review_joblisting', session_id=session_id))
            else:
                flash("Error: The uploaded zip file does not contain valid session data.")
                return redirect(url_for('home'))

        except zipfile.BadZipFile:
            flash("Error: The uploaded file is not a valid zip file.")
            return redirect(url_for('home'))
        except Exception as e:
            flash(f"An error occurred while processing the bundle: {e}")
            return redirect(url_for('home'))
    else:
        flash("Error: Invalid file type. Please upload a .zip session bundle.")
        return redirect(url_for('home'))

@app.route('/review/joblisting/<session_id>')
def review_joblisting(session_id):
    """Displays the scraped markdown content for the user to review and edit."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    markdown_path = os.path.join(session_path, "job_posting.md")
    try:
        with open(markdown_path, "r", encoding="utf-8") as f:
            content = f.read()
        return render_template(
            'review_joblisting.html', 
            markdown_content=content, 
            session_id=session_id, 
            config=CONFIG, 
            prompt=JOB_ANALYSIS_PROMPT  # Updated prompt
        )
    except FileNotFoundError:
        flash("Error: Could not find the scraped content. Please try again.")
        return redirect(url_for('home'))

@app.route('/save/markdown/<session_id>', methods=['POST'])
def save_markdown(session_id):
    """Saves the edited markdown content to the job_posting.md file."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    markdown_path = os.path.join(session_path, "job_posting.md")
    
    try:
        edited_content = request.form.get('markdown_content', '').strip()
        
        if not edited_content:
            flash("Error: Cannot save empty content.")
            return redirect(url_for('review_joblisting', session_id=session_id))
        
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(edited_content)
        
        flash("✅ Changes saved successfully!")
        return redirect(url_for('review_joblisting', session_id=session_id))
        
    except Exception as e:
        flash(f"Error saving changes: {e}")
        return redirect(url_for('review_joblisting', session_id=session_id))

@app.route('/reset/markdown/<session_id>', methods=['POST'])
def reset_markdown(session_id):
    """Resets the markdown by reloading from the saved job_posting.md file."""
    flash("🔄 Content reset to saved version.")
    return redirect(url_for('review_joblisting', session_id=session_id))

@app.route('/run/analysis/<session_id>', methods=['POST'])
def run_step2_analysis(session_id):
    """Runs the AI job analysis (Step 2) and redirects to the next review page. UPDATED for Resume Builder."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    try:
        analyze_job_posting(session_path, client, CONFIG["openai_model"])  # Now creates ideal_candidate_profile.json
        return redirect(url_for('review_jobanalysis', session_id=session_id))
    except Exception as e:
        flash(f"An error occurred during job analysis: {e}")
        return redirect(url_for('review_joblisting', session_id=session_id))

@app.route('/review/jobanalysis/<session_id>')
def review_jobanalysis(session_id):
    """Displays the job analysis and handles user profile upload. UPDATED for Resume Builder."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    
    # Try to load the new ideal_candidate_profile.json first, fall back to legacy
    ideal_profile_path = os.path.join(session_path, "ideal_candidate_profile.json")
    legacy_analysis_path = os.path.join(session_path, "structured_job_data.json")
    markdown_path = os.path.join(session_path, "job_posting.md")
    
    try:
        # Load analysis data (prefer new format)
        if os.path.exists(ideal_profile_path):
            with open(ideal_profile_path, "r", encoding="utf-8") as f:
                analysis_data = json.load(f)
                pretty_json = json.dumps(analysis_data, indent=4)
                # Extract keywords from the new format
                keywords = analysis_data.get("top_technical_skills", []) + analysis_data.get("top_soft_skills", [])
        elif os.path.exists(legacy_analysis_path):
            with open(legacy_analysis_path, "r", encoding="utf-8") as f:
                analysis_data = json.load(f)
                pretty_json = json.dumps(analysis_data, indent=4)
                keywords = analysis_data.get("keywords", [])
        else:
            flash("Error: Could not find analysis data. Please run analysis first.")
            return redirect(url_for('review_joblisting', session_id=session_id))
            
        # Load markdown content
        with open(markdown_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
        
        return render_template(
            'review_jobanalysis.html',
            json_content=pretty_json,
            markdown_content=markdown_content,
            session_id=session_id,
            config=CONFIG,
            prompt=WORK_EXPERIENCE_PROMPT,  # Updated prompt
            keywords=keywords
        )
    except FileNotFoundError as e:
        flash(f"Error: Could not find required files. {e}")
        return redirect(url_for('home'))

@app.route('/run/tailoring/<session_id>', methods=['POST'])
def run_step3_tailoring(session_id):
    """Handles user profile upload and runs the Resume Builder pipeline. UPDATED for Resume Builder."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    user_profile_path = os.path.join(session_path, "user_profile.json")  # Changed from base_resume.json
    
    try:
        # 1. Handle the user profile file
        profile_file = request.files.get('resume_file')  # Form field name stays the same for compatibility
        if profile_file and profile_file.filename:
            # User uploaded a new profile, save it
            profile_file.save(user_profile_path)
            flash("✅ New user profile uploaded and saved.")
        elif not os.path.exists(user_profile_path):
            # No new file uploaded AND no file exists, so copy the default
            default_profile_src = "data/resume_assets/user_profile.json"  # Updated default location
            if not os.path.exists(default_profile_src):
                flash("Error: Default user profile not found on server.")
                return redirect(url_for('review_jobanalysis', session_id=session_id))
            shutil.copy(default_profile_src, user_profile_path)
            flash("ℹ️ Using default user profile.")

        # 2. Get the final list of keywords from the form
        final_keywords_str = request.form.get('final_keywords', '')
        keywords = [k.strip() for k in final_keywords_str.split(',') if k.strip()]
        
        # 3. Run the Resume Builder pipeline
        tailor_resume(
            session_path=session_path, 
            user_profile_path=user_profile_path,  # Updated parameter name
            client=client, 
            model_name=CONFIG["openai_model"], 
            api_parameters=CONFIG["openai_parameters"],
            keywords=keywords
        )
        return redirect(url_for('review_tailoring', session_id=session_id))
        
    except Exception as e:
        flash(f"An error occurred during resume building: {e}")
        return redirect(url_for('review_jobanalysis', session_id=session_id))


@app.route('/review/tailoring/<session_id>')
def review_tailoring(session_id):
    """Displays the built resume content for review. UPDATED labels for Resume Builder."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    tailored_path = os.path.join(session_path, "tailored_resume_content.json")
    
    # Try to load the ideal candidate profile, fall back to legacy job analysis
    ideal_profile_path = os.path.join(session_path, "ideal_candidate_profile.json")
    legacy_analysis_path = os.path.join(session_path, "structured_job_data.json")
    
    try:
        with open(tailored_path, "r", encoding="utf-8") as f:
            tailored_data = json.load(f)
            pretty_tailored_json = json.dumps(tailored_data, indent=4)
            
        # Load analysis data (prefer new format)
        if os.path.exists(ideal_profile_path):
            with open(ideal_profile_path, "r", encoding="utf-8") as f:
                analysis_data = json.load(f)
        elif os.path.exists(legacy_analysis_path):
            with open(legacy_analysis_path, "r", encoding="utf-8") as f:
                analysis_data = json.load(f)
        else:
            analysis_data = {"error": "Analysis data not found"}
            
        pretty_job_json = json.dumps(analysis_data, indent=4)
        
        return render_template(
            'review_tailoring.html',
            tailored_content=pretty_tailored_json,
            job_analysis_content=pretty_job_json,
            session_id=session_id,
            config=CONFIG
        )
    except FileNotFoundError:
        flash("Error: Could not find the built resume data.")
        return redirect(url_for('home'))

@app.route('/save/ideal_profile/<session_id>', methods=['POST'])
def save_ideal_profile(session_id):
    """Saves the edited ideal candidate profile JSON content."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    json_path = os.path.join(session_path, "ideal_candidate_profile.json")
    
    try:
        edited_content = request.form.get('ideal_profile_content', '').strip()
        if not edited_content:
            flash("Error: Cannot save empty content.")
            return redirect(url_for('review_jobanalysis', session_id=session_id))
        
        # IMPORTANT: Validate that the string is valid JSON before saving
        try:
            parsed_json = json.loads(edited_content)
            # Re-serialize with indentation for clean storage
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(parsed_json, f, indent=4)
            flash("✅ Ideal candidate profile saved successfully!")
        except json.JSONDecodeError:
            flash("Error: Invalid JSON format. Please correct the syntax and try again.")

    except Exception as e:
        flash(f"Error saving changes: {e}")
        
    return redirect(url_for('review_jobanalysis', session_id=session_id))

@app.route('/reset/ideal_profile/<session_id>', methods=['POST'])
def reset_ideal_profile(session_id):
    """Resets the ideal candidate profile by reloading the page."""
    flash("🔄 Ideal candidate profile reset to saved version.")
    return redirect(url_for('review_jobanalysis', session_id=session_id))

@app.route('/save/json/<session_id>', methods=['POST'])
def save_json(session_id):
    """Saves the edited built resume JSON content."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    json_path = os.path.join(session_path, "tailored_resume_content.json")
    
    try:
        edited_content = request.form.get('json_content', '').strip()
        if not edited_content:
            flash("Error: Cannot save empty content.")
            return redirect(url_for('review_tailoring', session_id=session_id))
        
        # IMPORTANT: Validate that the string is valid JSON before saving
        try:
            parsed_json = json.loads(edited_content)
            # Re-serialize with indentation for clean storage
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(parsed_json, f, indent=4)
            flash("✅ Changes saved successfully!")
        except json.JSONDecodeError:
            flash("Error: Invalid JSON format. Please correct the syntax and try again.")

    except Exception as e:
        flash(f"Error saving changes: {e}")
        
    return redirect(url_for('review_tailoring', session_id=session_id))

@app.route('/reset/json/<session_id>', methods=['POST'])
def reset_json(session_id):
    """Resets the JSON by reloading the page."""
    flash("🔄 Content reset to saved version.")
    return redirect(url_for('review_tailoring', session_id=session_id))

@app.route('/run/final_steps/<session_id>', methods=['POST'])
def run_final_steps(session_id):
    """Generates the PDF and then runs the ATS validation score. UPDATED for Resume Builder."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    user_profile_path = os.path.join(session_path, "user_profile.json")  # Updated from base_resume.json
    
    if not os.path.exists(user_profile_path):
        flash("Error: User profile not found for this session.")
        return redirect(url_for('review_jobanalysis', session_id=session_id))
    
    try:
        # Step 4: Generate PDF
        generate_pdf(session_path, user_profile_path, CONFIG["pdf_config"])  # Updated parameter
        
        # Step 5: Run ATS Scorer
        score_resume(session_path, client, CONFIG["openai_model"])

        flash("✅ Successfully generated PDF and ATS report!")
        return redirect(url_for('review_final', session_id=session_id))
        
    except Exception as e:
        flash(f"An error occurred during the final steps: {e}")
        return redirect(url_for('review_tailoring', session_id=session_id))

@app.route('/review/final/<session_id>')
def review_final(session_id):
    """Displays the final ATS score and report."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    validation_path = os.path.join(session_path, "ats_validation.json")
    
    try:
        with open(validation_path, "r", encoding="utf-8") as f:
            ats_result = ATSValidationResult.model_validate_json(f.read())
            
        return render_template(
            'review_final.html',
            session_id=session_id,
            ats_result=ats_result
        )
    except FileNotFoundError:
        flash("Error: Could not find the ATS validation report. Please try generating it again.")
        return redirect(url_for('review_tailoring', session_id=session_id))
    except Exception as e:
        flash(f"An error occurred displaying the report: {e}")
        return redirect(url_for('home'))

@app.route('/download/pdf/<session_id>')
def download_pdf(session_id):
    """Downloads the generated PDF file."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    try:
        pdf_files = glob.glob(os.path.join(session_path, '*.pdf'))
        if not pdf_files:
            flash("Error: PDF file not found for this session.")
            return redirect(url_for('home'))
        return send_file(pdf_files[0], as_attachment=True)
    except Exception as e:
        flash(f"An error occurred while trying to download the file: {e}")
        return redirect(url_for('home'))

@app.route('/download/bundle/<session_id>')
def download_bundle(session_id):
    """Creates and downloads a zip bundle of the session files."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    zip_name = f"{session_id}_bundle.zip"
    zip_path = os.path.join(session_path, zip_name)

    try:
        # Create the zip file using our utility function
        created_zip_path = create_session_zip(session_path, zip_path)
        if not created_zip_path:
            flash("Error: Could not create session bundle, no files to zip.")
            return redirect(url_for('review_final', session_id=session_id))

        return send_file(created_zip_path, as_attachment=True, download_name=zip_name)
    except Exception as e:
        flash(f"An error occurred while creating the bundle: {e}")
        return redirect(url_for('review_final', session_id=session_id))

@app.route('/view/pdf/<session_id>')
def view_pdf(session_id):
    """Serves the PDF file for iframe viewing or direct linking."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    try:
        pdf_files = glob.glob(os.path.join(session_path, '*.pdf'))
        if not pdf_files:
            flash("Error: PDF file not found for this session.")
            return redirect(url_for('home'))
        return send_file(pdf_files[0], mimetype='application/pdf')
    except Exception as e:
        flash(f"An error occurred while trying to view the file: {e}")
        return redirect(url_for('home'))

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # Ensure required directories exist
    os.makedirs(CONFIG["output_base_dir"], exist_ok=True)
    os.makedirs("data/resume_assets", exist_ok=True) # Ensure resume assets dir exists
    
    # Clean up old sessions
    cleanup_old_sessions(CONFIG["output_base_dir"], days=30)
    
    app.run(debug=True)
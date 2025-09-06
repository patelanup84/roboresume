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

# --- IMPORTS FROM OUR FILES ---
from models import JobListing, ATSValidationResult
from config import CONFIG, ANALYSIS_PROMPT_TEXT, TAILORING_PROMPT_TEXT, ATS_PROMPT_TEXT
from utils import create_session_directory, cleanup_old_sessions

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
            prompt=ANALYSIS_PROMPT_TEXT
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
    """Runs the AI job analysis (Step 2) and redirects to the next review page."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    try:
        analyze_job_posting(session_path, client, CONFIG["openai_model"])
        return redirect(url_for('review_jobanalysis', session_id=session_id))
    except Exception as e:
        flash(f"An error occurred during job analysis: {e}")
        return redirect(url_for('review_joblisting', session_id=session_id))

@app.route('/review/jobanalysis/<session_id>')
def review_jobanalysis(session_id):
    """Displays the job analysis JSON and the original markdown for comparison."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    analysis_path = os.path.join(session_path, "structured_job_data.json")
    markdown_path = os.path.join(session_path, "job_posting.md")
    
    try:
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis_data = json.load(f)
            pretty_json = json.dumps(analysis_data, indent=4)
            keywords = analysis_data.get("keywords", []) # Extract keywords
        with open(markdown_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
        
        return render_template(
            'review_jobanalysis.html',
            json_content=pretty_json,
            markdown_content=markdown_content,
            session_id=session_id,
            config=CONFIG,
            prompt=TAILORING_PROMPT_TEXT,
            keywords=keywords # Pass keywords to template
        )
    except FileNotFoundError:
        flash("Error: Could not find the analysis data. Please try again.")
        return redirect(url_for('home'))

@app.route('/run/tailoring/<session_id>', methods=['POST'])
def run_step3_tailoring(session_id):
    """Handles resume submission and keyword finalization, then runs tailoring."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    base_resume_path = os.path.join(session_path, "base_resume.json")
    
    try:
        # 1. Handle the base resume file
        resume_file = request.files.get('resume_file')
        if resume_file and resume_file.filename:
            # User uploaded a new resume, save it
            resume_file.save(base_resume_path)
            flash("✅ New base resume uploaded and saved.")
        elif not os.path.exists(base_resume_path):
            # No new file uploaded AND no file exists, so copy the default
            default_resume_src = "data/resume_assets/base_resume.json"
            if not os.path.exists(default_resume_src):
                flash("Error: Default resume not found on server.")
                return redirect(url_for('review_jobanalysis', session_id=session_id))
            shutil.copy(default_resume_src, base_resume_path)
            flash("ℹ️ Using default base resume.")

        # 2. Get the final list of keywords from the form
        final_keywords_str = request.form.get('final_keywords', '')
        keywords = [k.strip() for k in final_keywords_str.split(',') if k.strip()]
        
        # 3. Run the tailoring service
        tailor_resume(
            session_path=session_path, 
            base_resume_path=base_resume_path, 
            client=client, 
            model_name=CONFIG["openai_model"], 
            api_parameters=CONFIG["openai_parameters"],
            keywords=keywords
        )
        return redirect(url_for('review_tailoring', session_id=session_id))
        
    except Exception as e:
        flash(f"An error occurred during resume tailoring: {e}")
        return redirect(url_for('review_jobanalysis', session_id=session_id))


@app.route('/review/tailoring/<session_id>')
def review_tailoring(session_id):
    """Displays the tailored resume content for review."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    tailored_path = os.path.join(session_path, "tailored_resume_content.json")
    job_analysis_path = os.path.join(session_path, "structured_job_data.json")
    
    try:
        with open(tailored_path, "r", encoding="utf-8") as f:
            tailored_data = json.load(f)
            pretty_tailored_json = json.dumps(tailored_data, indent=4)
            
        with open(job_analysis_path, "r", encoding="utf-8") as f:
            job_data = json.load(f)
            pretty_job_json = json.dumps(job_data, indent=4)
        
        return render_template(
            'review_tailoring.html',
            tailored_content=pretty_tailored_json,
            job_analysis_content=pretty_job_json,
            session_id=session_id,
            config=CONFIG
        )
    except FileNotFoundError:
        flash("Error: Could not find the tailored resume data.")
        return redirect(url_for('home'))

@app.route('/save/json/<session_id>', methods=['POST'])
def save_json(session_id):
    """Saves the edited tailored resume JSON content."""
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
    """Generates the PDF and then runs the ATS validation score."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    base_resume_path = os.path.join(session_path, "base_resume.json")
    
    if not os.path.exists(base_resume_path):
        flash("Error: Base resume not found for this session.")
        return redirect(url_for('review_jobanalysis', session_id=session_id))
    
    try:
        # Step 4: Generate PDF
        generate_pdf(session_path, base_resume_path, CONFIG["pdf_config"])
        
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
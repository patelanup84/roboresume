import os
import instructor
import asyncio
import json
import glob
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
    """Handles form submission and starts the resume generation pipeline."""
    job_url = request.form.get('job_url', '').strip()
    job_description = request.form.get('job_description', '').strip()
    resume_file = request.files.get('resume_file')
    
    if not (job_url or job_description):
        flash("Error: Please provide either a job URL or job description.")
        return redirect(url_for('home'))
    
    if not resume_file or not resume_file.filename:
        flash("Error: Please upload a resume file.")
        return redirect(url_for('home'))
    
    # Extract company and position for session naming
    company = request.form.get('company', 'Unknown')
    position = request.form.get('position', 'Unknown')
    
    session_id = create_session_directory(CONFIG["output_base_dir"], company, position)
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    
    if not session_path:
        flash("Error: Could not create session directory.")
        return redirect(url_for('home'))
    
    base_resume_path = os.path.join(session_path, secure_filename(resume_file.filename))
    resume_file.save(base_resume_path)

    if job_url:
        source_config = {"type": "url", "url": job_url}
    elif job_description:
        source_config = {"type": "string", "text": job_description}
    else:
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
        # Get the edited content from the form
        edited_content = request.form.get('markdown_content', '').strip()
        
        if not edited_content:
            flash("Error: Cannot save empty content.")
            return redirect(url_for('review_joblisting', session_id=session_id))
        
        # Save the edited content
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
    try:
        flash("🔄 Content reset to saved version.")
        return redirect(url_for('review_joblisting', session_id=session_id))
        
    except Exception as e:
        flash(f"Error resetting content: {e}")
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
            # Template expects 'json_content' 
            pretty_json = json.dumps(analysis_data, indent=4)
        with open(markdown_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
        
        return render_template(
            'review_jobanalysis.html',
            json_content=pretty_json,  # Changed from analysis_data
            markdown_content=markdown_content,
            session_id=session_id,
            config=CONFIG,
            prompt=TAILORING_PROMPT_TEXT
        )
    except FileNotFoundError:
        flash("Error: Could not find the analysis data. Please try again.")
        return redirect(url_for('home'))

@app.route('/run/tailoring/<session_id>', methods=['POST'])
def run_step3_tailoring(session_id):
    """Runs the resume tailoring (Step 3) and redirects to the next review page."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    try:
        # Find the base resume file (assuming it's the only other .json)
        all_files = glob.glob(os.path.join(session_path, '*.*'))
        base_resume_path = None
        for file_path in all_files:
            if file_path.endswith('.json') and not file_path.endswith(('structured_job_data.json', 'tailored_resume_content.json', 'final_resume_data.json', 'ats_validation.json')):
                base_resume_path = file_path
                break
        
        if not base_resume_path:
            flash("Error: Could not find the base resume file.")
            return redirect(url_for('review_jobanalysis', session_id=session_id))
        
        tailor_resume(session_path, base_resume_path, client, CONFIG["openai_model"], CONFIG["openai_parameters"])
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

@app.route('/run/final_steps/<session_id>', methods=['POST'])
def run_final_steps(session_id):
    """Generates the PDF and then runs the ATS validation score."""
    session_path = os.path.join(CONFIG["output_base_dir"], session_id)
    try:
        # Find the base resume file
        all_files = glob.glob(os.path.join(session_path, '*.*'))
        base_resume_path = None
        for file_path in all_files:
            if file_path.endswith('.json') and not file_path.endswith(('structured_job_data.json', 'tailored_resume_content.json', 'final_resume_data.json', 'ats_validation.json')):
                base_resume_path = file_path
                break
        
        if not base_resume_path:
            flash("Error: Could not find the base resume file.")
            return redirect(url_for('review_tailoring', session_id=session_id))
        
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
            # Pydantic model can validate the data upon reading
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
    
    # Clean up old sessions
    cleanup_old_sessions(CONFIG["output_base_dir"], days=30)
    
    app.run(debug=True)

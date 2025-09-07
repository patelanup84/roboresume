# 🤖 RoboResume: AI-Powered Resume Tailoring

RoboResume is a web application built with Flask that automates the time-consuming process of tailoring a resume for a specific job application. It leverages the power of Large Language Models (LLMs) to analyze job descriptions, intelligently rewrite a base resume to align with key requirements, generate a professional PDF, and provide an ATS-style match score for the final document.

## ✨ Key Features

  * **Job Posting Ingestion**: Scrapes job descriptions directly from a provided URL or accepts pasted text.
  * **AI-Powered Analysis**: Uses AI to parse unstructured job descriptions and convert them into structured data, identifying the company name, position title, location, and key skills.
  * **Intelligent Resume Tailoring**: Rewrites a base resume's summary and work experience bullet points to strategically incorporate keywords and align with the target job's requirements.
  * **Interactive User Workflow**: A multi-step web interface guides the user through each stage of the process, allowing for review and manual edits to both the job analysis and the final resume content.
  * **Professional PDF Generation**: Assembles the tailored content into a clean, professional resume layout and generates a downloadable PDF file.
  * **ATS Match Scoring**: Provides a final "Applicant Tracking System"-style report that scores the resume's match percentage against the job description and highlights matching and missing keywords.
  * **Session Management**: Download the complete session (job description, analysis, tailored resume) as a single `.zip` bundle to save your progress. Upload the bundle later to resume from where you left off.

## 🛠️ Tech Stack

  * **Backend**: Flask
  * **AI Integration**: OpenAI API, Instructor, Pydantic
  * **Web Scraping**: Crawl4AI
  * **PDF Generation**: WeasyPrint, Jinja2
  * **Frontend**: Bootstrap, HTML5

## 🚀 Installation & Setup

Follow these steps to get RoboResume running on your local machine.

### Prerequisites

  * Python 3.8+
  * Git

### Instructions

1.  **Clone the repository:**
    Open your terminal and clone the project files.

    ```sh
    git clone <your-repository-url>
    cd roboresume
    ```

2.  **Create and activate a virtual environment:**
    It is highly recommended to use a virtual environment to manage dependencies.

      * On macOS / Linux:
        ```sh
        python3 -m venv venv
        source venv/bin/activate
        ```
      * On Windows:
        ```sh
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  **Install dependencies:**
    Install all the required Python packages from the `requirements.txt` file.

    ```sh
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a `.env` file by copying the example file. Then, add your OpenAI API key.

    ```sh
    cp .env.example .env
    ```

    Now, open the `.env` file in a text editor and add your key:

    ```
    OPENAI_API_KEY=your_openai_api_key_here
    ```

5.  **Run the application:**
    Start the Flask development server.

    ```sh
    python app.py
    ```

6.  **Access RoboResume:**
    Open your web browser and navigate to `http://127.0.0.1:5000`.

## 📋 Usage (User Flow)

The application supports two primary workflows: starting a new job analysis from scratch, or resuming a previous session from a downloaded `.zip` bundle.

1.  **Start or Resume a Session:** On the home page, you have two options:

      * **To Start a New Job:** Use the top panel to provide a job posting URL or paste the full job description into the text area. Click **"Analyze Job Posting"** to begin.
      * **To Resume a Previous Session:** Use the bottom panel to upload a `.zip` session bundle that you previously downloaded. The application will load the data and take you to the appropriate step.

2.  **Review Job Listing:** The application will display the scraped content as Markdown. You can edit this text to clean up any scraping errors or remove irrelevant information. Once satisfied, click **"Run Analysis"** to proceed to the next step.

3.  **Review AI Analysis & Keywords:** This page shows the structured JSON data extracted by the AI. Here you can:

      * Upload a custom `base_resume.json` file (optional).
      * Add, edit, or remove keywords that you want the AI to focus on during tailoring.
      * Click **"Run Tailoring"** to have the AI rewrite your resume content.

4.  **Review Tailored Resume:** The AI-generated resume content is displayed in an editable JSON format. Make any final manual adjustments to the summary or work experience bullet points. When ready, click **"Generate PDF & Report"**.

5.  **View Final Report & Download:** The final page displays the ATS match score and a summary of matching/missing keywords. You can now **"Preview PDF"**, **"Download PDF"**, or **"Download Session (.zip)"** to save the entire project bundle for later use.

## 📁 Project Structure

The project is organized into several key directories and files:

```
.
├── .env.example
├── app.py
├── config.py
├── models.py
├── requirements.txt
├── services/
│   ├── job_analyzer.py
│   ├── pdf_generator.py
│   ├── resume_scorer.py
│   └── resume_tailor.py
├── templates/
│   ├── index.html
│   ├── review_final.html
│   ├── review_jobanalysis.html
│   └── ... (other html files)
└── utils.py
```

  * `app.py`: The main Flask application file. It defines all the web routes and orchestrates the calls to the different services for each step in the workflow.
  * `config.py`: Stores all configuration constants, including the OpenAI model name, file paths, and, most importantly, the system prompts used to instruct the AI for analysis, tailoring, and scoring.
  * `models.py`: Defines the Pydantic data models (`JobListing`, `TailoredResumeContent`, etc.) that provide a strict structure for the data returned by the AI, ensuring reliable and predictable outputs.
  * `requirements.txt`: Lists all the Python dependencies required to run the project.
  * `services/`: A directory containing modules that handle the core logic of the application. Each file is responsible for a specific step in the pipeline (e.g., analyzing the job, tailoring the resume).
  * `templates/`: Contains all the HTML files used for the frontend user interface. Each page in the application's workflow corresponds to a template file.
  * `utils.py`: A collection of shared utility functions, such as creating session directories and sanitizing text for file paths.
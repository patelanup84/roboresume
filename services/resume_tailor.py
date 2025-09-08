"""
Resume building service - handles intelligent resume construction from user profile
COMPLETELY REWRITTEN for Resume Builder architecture
"""

import os
import json
from typing import Dict, Any, Optional, Tuple, List
from openai import OpenAI

# Local imports
from models import IdealCandidateProfile, GeneratedResume, GeneratedWorkExperience, GeneratedSkill
from config import WORK_EXPERIENCE_PROMPT, SKILLS_PROMPT, SUMMARY_PROMPT


def tailor_resume(session_path: str, user_profile_path: str, client: OpenAI, model_name: str, api_parameters: dict, keywords: List[str] = None) -> str:
    """
    Main entry point - orchestrates the 4-step Resume Builder pipeline.
    REWRITTEN for Resume Builder architecture.
    
    Args:
        session_path: Path to session directory
        user_profile_path: Path to user_profile.json file
        client: OpenAI client
        model_name: AI model to use
        api_parameters: API parameters for OpenAI calls
        keywords: Additional keywords to focus on (optional)
    
    Returns:
        Path to generated resume content file
    """
    print("\n=== Resume Builder Pipeline ===")
    
    # Load the ideal candidate profile from job analysis
    ideal_profile_path = os.path.join(session_path, "ideal_candidate_profile.json")
    with open(ideal_profile_path, "r", encoding="utf-8") as f:
        ideal_profile = IdealCandidateProfile.model_validate_json(f.read())
    
    # Load user profile
    with open(user_profile_path, "r", encoding="utf-8") as f:
        user_profile = json.load(f)
    
    # Load original job description for context
    job_posting_path = os.path.join(session_path, "job_posting.md")
    with open(job_posting_path, "r", encoding="utf-8") as f:
        job_description = f.read()
    
    # Execute the 4-step pipeline
    print("🔄 Step 1: Building Work Experience...")
    work_experience = _build_work_experience(user_profile, ideal_profile, job_description, client, model_name, api_parameters, keywords)
    
    print("🔄 Step 2: Building Skills Section...")
    skills = _build_skills(user_profile, ideal_profile, client, model_name, api_parameters)
    
    print("🔄 Step 3: Writing Summary...")
    summary = _build_summary(work_experience, skills, ideal_profile, client, model_name, api_parameters)
    
    print("🔄 Step 4: Assembling Final Resume...")
    # Assemble the final resume content
    final_resume_content = {
        "summary": summary,
        "work_experience": [exp.model_dump() for exp in work_experience],
        "education": user_profile.get("education", []),  # Pull education directly from profile
        "skills": [skill.model_dump() for skill in skills],
        "projects": user_profile.get("projects", []),  # Pull projects directly from profile
        "target_role": ideal_profile.experience_summary
    }
    
    # Save the generated content
    output_path = os.path.join(session_path, "tailored_resume_content.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_resume_content, f, indent=4)
    
    print(f"✅ Resume Builder Pipeline Complete! Saved to: {output_path}")
    return output_path


# ============================================================================
# RESUME BUILDER PIPELINE STEPS
# ============================================================================

def _build_work_experience(user_profile: dict, ideal_profile: IdealCandidateProfile, job_description: str, client: OpenAI, model_name: str, api_parameters: dict, keywords: List[str] = None) -> List[GeneratedWorkExperience]:
    """
    Step 1: Intelligently selects and rewrites work experience from user profile.
    """
    try:
        # Prepare keyword injection if keywords are provided
        keyword_injection = ""
        if keywords:
            keyword_list = ", ".join(keywords)
            keyword_injection = f"\n\n**Additional Keywords to Prioritize:** {keyword_list}"
        
        # Prepare the comprehensive prompt
        user_prompt = (
            f"**Ideal Candidate Profile:**\n{ideal_profile.model_dump_json(indent=2)}\n\n"
            f"**User's Full Profile (for achievement selection):**\n{json.dumps(user_profile, indent=2)}\n\n"
            f"**Original Job Description (for keyword alignment):**\n{job_description}{keyword_injection}"
        )
        
        response = client.chat.completions.create(
            model=model_name,
            response_model=GeneratedResume,  # Use full resume model to get work_experience
            messages=[
                {"role": "system", "content": WORK_EXPERIENCE_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            **api_parameters
        )
        
        return response.work_experience
        
    except Exception as e:
        print(f"❌ Error building work experience: {str(e)}")
        raise


def _build_skills(user_profile: dict, ideal_profile: IdealCandidateProfile, client: OpenAI, model_name: str, api_parameters: dict) -> List[GeneratedSkill]:
    """
    Step 2: Builds the skills section based on user profile and ideal candidate requirements.
    """
    try:
        user_prompt = (
            f"**Ideal Candidate Profile:**\n{ideal_profile.model_dump_json(indent=2)}\n\n"
            f"**User's Full Profile (for skill selection):**\n{json.dumps(user_profile, indent=2)}"
        )
        
        response = client.chat.completions.create(
            model=model_name,
            response_model=GeneratedResume,  # Use full resume model to get skills
            messages=[
                {"role": "system", "content": SKILLS_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            **api_parameters
        )
        
        return response.skills
        
    except Exception as e:
        print(f"❌ Error building skills: {str(e)}")
        raise


def _build_summary(work_experience: List[GeneratedWorkExperience], skills: List[GeneratedSkill], ideal_profile: IdealCandidateProfile, client: OpenAI, model_name: str, api_parameters: dict) -> str:
    """
    Step 3: Writes the professional summary based on the already-built sections.
    """
    try:
        # Show the AI the content we've already decided to include in the resume
        built_sections = {
            "work_experience": [exp.model_dump() for exp in work_experience],
            "skills": [skill.model_dump() for skill in skills]
        }
        
        user_prompt = (
            f"**Ideal Candidate Profile:**\n{ideal_profile.model_dump_json(indent=2)}\n\n"
            f"**Built Resume Sections (for synthesis):**\n{json.dumps(built_sections, indent=2)}"
        )
        
        response = client.chat.completions.create(
            model=model_name,
            response_model=GeneratedResume,  # Use full resume model to get summary
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            **api_parameters
        )
        
        return response.summary
        
    except Exception as e:
        print(f"❌ Error building summary: {str(e)}")
        raise


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _calculate_tag_relevance_score(achievement_tags: List[str], ideal_skills: List[str]) -> float:
    """
    Calculates how well an achievement's tags align with the ideal candidate profile.
    This can be used for more sophisticated achievement selection logic in the future.
    """
    if not achievement_tags or not ideal_skills:
        return 0.0
    
    # Convert to lowercase for case-insensitive matching
    achievement_tags_lower = [tag.lower() for tag in achievement_tags]
    ideal_skills_lower = [skill.lower() for skill in ideal_skills]
    
    # Count matches
    matches = sum(1 for tag in achievement_tags_lower if any(skill in tag or tag in skill for skill in ideal_skills_lower))
    
    # Return score as percentage
    return matches / len(achievement_tags) if achievement_tags else 0.0


def _extract_keywords_from_profile(ideal_profile: IdealCandidateProfile) -> List[str]:
    """
    Extracts all relevant keywords from the ideal candidate profile.
    """
    keywords = []
    keywords.extend(ideal_profile.top_technical_skills)
    keywords.extend(ideal_profile.top_soft_skills)
    return keywords


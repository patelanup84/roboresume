# Standard library imports
from typing import Any, Dict, List, Literal, Optional

# Third-party imports
from pydantic import BaseModel, Field, HttpUrl

# --------------------------------------------------------------------------
# Resume Builder Data Models
# --------------------------------------------------------------------------

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
    location: Optional[str] = None
    technologies: Optional[List[str]] = Field(default_factory=list)

class GeneratedSkill(BaseModel):
    category: str
    entries: List[str]

class GeneratedResume(BaseModel):
    """The final, assembled resume content, ready for PDF generation."""
    summary: str
    work_experience: List[GeneratedWorkExperience]
    skills: List[GeneratedSkill]
    target_role: str

# --------------------------------------------------------------------------
# Legacy Data Models (Keep for compatibility)
# --------------------------------------------------------------------------

class JobListing(BaseModel):
    company_name: Optional[str] = None
    position_title: Optional[str] = None
    job_url: Optional[HttpUrl] = None
    description: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    work_location: Optional[Literal["remote", "in_person", "hybrid"]] = None
    employment_type: Optional[Literal["full_time", "part_time", "co_op", "internship", "contract"]] = None

class WorkExperienceContent(BaseModel):
    company: str
    position: str
    date: str
    description: List[str]
    location: Optional[str] = None
    technologies: Optional[List[str]] = Field(default_factory=list)

class EducationContent(BaseModel):
    school: str
    degree: str
    field: Optional[str] = None
    date: Optional[str] = None
    gpa: Optional[str] = None
    achievements: Optional[List[str]] = Field(default_factory=list)

class ProjectContent(BaseModel):
    name: str
    description: List[str]
    technologies: Optional[List[str]] = Field(default_factory=list)
    date: Optional[str] = None
    url: Optional[str] = None
    github_url: Optional[str] = None

class SkillContent(BaseModel):
    category: str
    entries: List[str]

class TailoredResumeContent(BaseModel):
    summary: Optional[str] = None
    work_experience: Optional[List[WorkExperienceContent]] = None
    education: Optional[List[EducationContent]] = None
    skills: Optional[List[SkillContent]] = None
    projects: Optional[List[ProjectContent]] = None
    target_role: str

class ATSValidationResult(BaseModel):
    match_score: int = Field(description="A score from 0 to 100 representing how well the resume matches the job description.")
    matching_keywords: List[str] = Field(description="A list of 5-7 keywords found in both the job description and the resume.")
    missing_keywords: List[str] = Field(description="A list of the 5-7 most important keywords from the job description that are missing from the resume.")
    summary: str = Field(description="A brief, 2-3 sentence summary explaining the score and key observations.")
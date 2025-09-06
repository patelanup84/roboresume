# Standard library imports
from typing import Any, Dict, List, Literal, Optional

# Third-party imports
from pydantic import BaseModel, Field, HttpUrl

# --------------------------------------------------------------------------
# Pydantic Data Models (EXTRACTED FROM jobbot resume_pipeline.py)
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
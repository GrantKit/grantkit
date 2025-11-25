"""Registry of NSF program configurations and requirements."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class SectionRequirement:
    """Requirement for a proposal section."""
    id: str
    title: str
    required: bool = True
    page_limit: Optional[int] = None
    word_limit: Optional[int] = None
    description: Optional[str] = None
    validation_rules: List[str] = field(default_factory=list)


@dataclass 
class ProgramConfig:
    """Complete configuration for an NSF program."""
    program_id: str
    name: str
    description: str
    deadline_info: str
    budget_cap: float
    project_period_years: int
    
    # Requirements
    sections: List[SectionRequirement] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)
    
    # Budget constraints
    indirect_rate_max: float = 0.25
    equipment_threshold: float = 5000.0
    
    # Formatting requirements
    page_limit_total: Optional[int] = None
    font_size_min: int = 10
    margins_min: float = 1.0
    
    # Special rules
    validation_rules: List[str] = field(default_factory=list)
    special_requirements: List[str] = field(default_factory=list)
    
    # Metadata
    solicitation_url: Optional[str] = None
    created_date: Optional[str] = None


class ProgramRegistry:
    """Registry for NSF program configurations."""
    
    def __init__(self):
        """Initialize with built-in program configurations."""
        self.programs: Dict[str, ProgramConfig] = {}
        self._load_builtin_programs()
        
    def _load_builtin_programs(self) -> None:
        """Load built-in program configurations."""
        # POSE Phase II
        pose_sections = [
            SectionRequirement(
                id="project_summary",
                title="Project Summary (with Keywords)",
                required=True,
                page_limit=1,
                description="Overview of the project with keywords"
            ),
            SectionRequirement(
                id="context_of_ose",
                title="Context of OSE",
                required=True,
                description="Context and background of the open-source ecosystem"
            ),
            SectionRequirement(
                id="ecosystem_establishment",
                title="Ecosystem Establishment/Growth",
                required=True,
                description="Plans for establishing and growing the ecosystem"
            ),
            SectionRequirement(
                id="organization_governance",
                title="Organization and Governance", 
                required=True,
                description="Organizational structure and governance model"
            ),
            SectionRequirement(
                id="continuous_development",
                title="Continuous Development Model",
                required=True,
                description="Model for ongoing development and maintenance"
            ),
            SectionRequirement(
                id="risk_security",
                title="Risk Analysis / Security Plan",
                required=True,
                description="Risk assessment and security considerations"
            ),
            SectionRequirement(
                id="community_building",
                title="Community Building",
                required=True,
                description="Strategies for building and engaging community"
            ),
            SectionRequirement(
                id="sustainability",
                title="Sustainability",
                required=True,
                description="Long-term sustainability plan"
            ),
            SectionRequirement(
                id="evaluation_plan",
                title="Evaluation Plan and Metrics",
                required=True,
                description="Methods for evaluating success"
            ),
            SectionRequirement(
                id="broader_impacts",
                title="Broader Impacts",
                required=True,
                description="Broader impacts of the project (NSF requirement)"
            ),
            SectionRequirement(
                id="conclusion",
                title="Conclusion and Roadmap",
                required=True,
                description="Summary and future roadmap"
            )
        ]
        
        pose_config = ProgramConfig(
            program_id="pose-phase-2",
            name="NSF POSE — Phase II",
            description="Pathways to Enable Open-Source Ecosystems Phase II",
            deadline_info="Varies by cohort - check NSF website",
            budget_cap=1_500_000,
            project_period_years=2,
            sections=pose_sections,
            attachments=[
                "References Cited",
                "Biographical Sketches (SciENcv) for Senior Personnel", 
                "Budget and Budget Justification",
                "Current and Pending (Other) Support",
                "Facilities, Equipment, and Other Resources",
                "Data Management and Sharing Plan (2 pages)",
                "Postdoctoral Mentoring Plan (if applicable, 1 page)",
                "Letters of Collaboration from 3–5 current users/contributors (≤2 pages each)",
                "Project Personnel, Collaborators and Partner Organizations list (Supplementary)"
            ],
            page_limit_total=15,
            indirect_rate_max=0.15,  # POSE-specific lower rate
            validation_rules=[
                "no_cloud_storage_links",
                "no_email_addresses", 
                "broader_impacts_required"
            ],
            solicitation_url="https://www.nsf.gov/pubs/2023/nsf23617/nsf23617.htm",
            created_date=datetime.now().isoformat()
        )
        
        self.programs["pose-phase-2"] = pose_config
        
        # CSSI - Collaborative Research in Computational and Data-Enabled Science
        cssi_sections = [
            SectionRequirement(
                id="project_summary",
                title="Project Summary",
                required=True,
                page_limit=1
            ),
            SectionRequirement(
                id="project_description",
                title="Project Description",
                required=True,
                page_limit=15,
                description="Main technical description"
            ),
            SectionRequirement(
                id="broader_impacts",
                title="Broader Impacts",
                required=True,
                description="Required NSF broader impacts section"
            ),
            SectionRequirement(
                id="prior_support",
                title="Results from Prior NSF Support",
                required=False,
                page_limit=5,
                description="If applicable"
            )
        ]
        
        cssi_config = ProgramConfig(
            program_id="cssi",
            name="Cyberinfrastructure for Sustained Scientific Innovation (CSSI)",
            description="Collaborative Research in Computational and Data-Enabled Science",
            deadline_info="Annual deadline - typically October",
            budget_cap=5_000_000,  # Higher cap for large collaborations
            project_period_years=5,
            sections=cssi_sections,
            attachments=[
                "References Cited",
                "Biographical Sketches",
                "Budget and Budget Justification",
                "Current and Pending Support",
                "Facilities, Equipment, and Other Resources",
                "Data Management Plan",
                "Software Management Plan"
            ],
            page_limit_total=15,
            validation_rules=[
                "software_plan_required",
                "broader_impacts_required"
            ],
            solicitation_url="https://www.nsf.gov/pubs/2023/nsf23610/nsf23610.htm"
        )
        
        self.programs["cssi"] = cssi_config
        
        # CAREER - Faculty Early Career Development Program
        career_sections = [
            SectionRequirement(
                id="project_summary",
                title="Project Summary", 
                required=True,
                page_limit=1
            ),
            SectionRequirement(
                id="career_development_plan",
                title="CAREER Development Plan",
                required=True,
                page_limit=5,
                description="Integration of research and education"
            ),
            SectionRequirement(
                id="research_plan",
                title="Research Plan",
                required=True,
                page_limit=10,
                description="Technical research description"
            ),
            SectionRequirement(
                id="broader_impacts",
                title="Broader Impacts",
                required=True,
                description="Required NSF broader impacts section"
            )
        ]
        
        career_config = ProgramConfig(
            program_id="career",
            name="Faculty Early Career Development Program (CAREER)",
            description="NSF's most prestigious award for early-career faculty",
            deadline_info="Annual deadline - varies by directorate",
            budget_cap=500_000,
            project_period_years=5,
            sections=career_sections,
            page_limit_total=15,
            validation_rules=[
                "career_development_required",
                "education_integration_required",
                "broader_impacts_required"
            ],
            special_requirements=[
                "Applicant must be untenured assistant professor",
                "Must integrate research and education",
                "Institution must provide tenure-track position"
            ],
            solicitation_url="https://www.nsf.gov/pubs/2023/nsf23690/nsf23690.htm"
        )
        
        self.programs["career"] = career_config
        
        logger.info(f"Loaded {len(self.programs)} built-in program configurations")
        
    def get_program(self, program_id: str) -> Optional[ProgramConfig]:
        """Get program configuration by ID."""
        return self.programs.get(program_id)
        
    def list_programs(self) -> List[str]:
        """Get list of available program IDs."""
        return list(self.programs.keys())
        
    def get_program_names(self) -> Dict[str, str]:
        """Get mapping of program IDs to names."""
        return {pid: config.name for pid, config in self.programs.items()}
        
    def add_program(self, config: ProgramConfig) -> None:
        """Add a custom program configuration."""
        self.programs[config.program_id] = config
        logger.info(f"Added program configuration: {config.program_id}")
        
    def load_from_yaml(self, yaml_path: Path) -> None:
        """Load program configuration from YAML file."""
        if not yaml_path.exists():
            raise FileNotFoundError(f"Program config not found: {yaml_path}")
            
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                
            # Parse sections
            sections = []
            for section_data in data.get('sections', []):
                section = SectionRequirement(
                    id=section_data.get('id', ''),
                    title=section_data.get('title', 'Untitled'),
                    required=section_data.get('required', True),
                    page_limit=section_data.get('page_limit'),
                    word_limit=section_data.get('word_limit'),
                    description=section_data.get('description'),
                    validation_rules=section_data.get('validation_rules', [])
                )
                sections.append(section)
                
            # Create program config
            basic_info = data.get('basic_info', {})
            config = ProgramConfig(
                program_id=data.get('program_id', yaml_path.stem),
                name=basic_info.get('program', 'Custom Program'),
                description=data.get('description', ''),
                deadline_info=basic_info.get('deadline', ''),
                budget_cap=data.get('budget_cap', 1_000_000),
                project_period_years=data.get('project_period_years', 3),
                sections=sections,
                attachments=data.get('attachments', []),
                page_limit_total=data.get('page_limit_total'),
                validation_rules=data.get('validation_rules', []),
                special_requirements=data.get('special_requirements', []),
                solicitation_url=data.get('solicitation_url')
            )
            
            self.add_program(config)
            
        except Exception as e:
            raise ValueError(f"Failed to load program config from {yaml_path}: {e}")
            
    def export_template(self, program_id: str, output_dir: Path) -> None:
        """Export template files for a program."""
        config = self.get_program(program_id)
        if not config:
            raise ValueError(f"Program not found: {program_id}")
            
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate config file
        config_data = {
            'basic_info': {
                'program': config.name,
                'project_title': 'Your Project Title Here',
                'organization_name': 'Your Institution',
                'deadline': config.deadline_info
            },
            'sections': [
                {
                    'id': section.id,
                    'title': section.title,
                    'file': f'sections/{section.id}.md',
                    'required': section.required,
                    'page_limit': section.page_limit,
                    'word_limit': section.word_limit
                }
                for section in config.sections
            ],
            'attachments': config.attachments,
            'budget_cap': config.budget_cap
        }
        
        config_path = output_dir / 'nsf_config.yaml'
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
            
        # Create sections directory and templates
        sections_dir = output_dir / 'sections'
        sections_dir.mkdir(exist_ok=True)
        
        for section in config.sections:
            section_file = sections_dir / f'{section.id}.md'
            if not section_file.exists():
                template_content = f"""# {section.title}

{section.description or 'Describe this section here.'}

<!-- 
Requirements:
- Required: {'Yes' if section.required else 'No'}
{f'- Page limit: {section.page_limit}' if section.page_limit else ''}
{f'- Word limit: {section.word_limit}' if section.word_limit else ''}
-->

[Write your content here...]
"""
                section_file.write_text(template_content, encoding='utf-8')
                
        # Create budget template
        budget_dir = output_dir / 'budget'
        budget_dir.mkdir(exist_ok=True)
        
        budget_template = {
            'A_senior_personnel': [
                {'description': 'PI salary (X months)', 'amount': 50000}
            ],
            'B_other_personnel': [
                {'description': 'Graduate student (1.0 FTE)', 'amount': 60000}
            ],
            'C_fringe': [
                {'description': 'Fringe benefits', 'amount': 27500}
            ],
            'E_travel': [
                {
                    'description': 'Conference travel',
                    'travelers': 2,
                    'days': 4,
                    'destination': {
                        'city': 'San Francisco',
                        'state': 'CA',
                        'fy': 2026,
                        'month': 6
                    },
                    'airfare': 600
                }
            ],
            'I_indirect': [
                {'rate': config.indirect_rate_max}
            ]
        }
        
        budget_path = budget_dir / 'budget.yaml'
        with open(budget_path, 'w', encoding='utf-8') as f:
            yaml.dump(budget_template, f, default_flow_style=False)
            
        logger.info(f"Exported {program_id} template to {output_dir}")
        
    def validate_program_compliance(self, program_id: str, content: str) -> List[str]:
        """Validate content against program-specific rules."""
        config = self.get_program(program_id)
        if not config:
            return [f"Unknown program: {program_id}"]
            
        issues = []
        
        # Check validation rules
        for rule in config.validation_rules:
            if rule == "broader_impacts_required":
                if "broader impact" not in content.lower():
                    issues.append("Broader impacts section not found")
                    
            elif rule == "no_email_addresses":
                import re
                if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content):
                    issues.append("Email addresses found in content")
                    
            elif rule == "no_cloud_storage_links":
                cloud_domains = ['dropbox', 'drive.google', 'onedrive']
                if any(domain in content.lower() for domain in cloud_domains):
                    issues.append("Cloud storage links found")
                    
        return issues
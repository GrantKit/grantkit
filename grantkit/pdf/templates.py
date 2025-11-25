"""LaTeX template management for NSF-compliant PDFs."""

from pathlib import Path
from typing import Dict, Optional


class LaTeXTemplateManager:
    """Manages LaTeX templates for NSF proposal generation."""
    
    def __init__(self):
        self.template_dir = Path(__file__).parent / "templates"
        self.template_dir.mkdir(exist_ok=True)
        
    def get_nsf_template(self, optimize_space: bool = True) -> str:
        """Get NSF-optimized LaTeX template."""
        if optimize_space:
            return self._get_space_optimized_template()
        else:
            return self._get_standard_template()
    
    def _get_space_optimized_template(self) -> str:
        """LaTeX template optimized to maximize content within NSF PAPPG 24-1 requirements."""
        return r"""
% NSF PAPPG 24-1 Compliant Document Template
% Optimized for maximum content within NSF requirements
% References: https://www.nsf.gov/pubs/policydocs/pappguide/nsf24001/index.jsp

\documentclass[10pt]{article}  % PAPPG 24-1 II.C.2.d.i.(a): 10pt minimum font size

% NSF-compliant packages and settings
\usepackage[letterpaper, margin=1in]{geometry}  % PAPPG 24-1 II.C.2.d.i.(c): 1-inch margins required
\usepackage{times}  % PAPPG 24-1 II.C.2.d.i.(a): Times New Roman or equivalent required
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{microtype}  % Better typography and space optimization
\usepackage{setspace}
\usepackage{titlesec}
\usepackage{parskip}
\usepackage{graphicx}
\usepackage{float}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{enumitem}
\usepackage{amsmath}
\usepackage{amsfonts}
\usepackage{url}
\usepackage[hidelinks]{hyperref}

% Font size and spacing optimization - PAPPG 24-1 II.C.2.d.i.(a)(b)
\renewcommand{\normalsize}{\fontsize{10}{12}\selectfont}  % 10pt font, optimized line spacing
\renewcommand{\small}{\fontsize{9}{10.8}\selectfont}  % For captions per PAPPG exception
\renewcommand{\footnotesize}{\fontsize{8}{9.6}\selectfont}  % For references per PAPPG exception

% Minimize paragraph spacing while maintaining readability - PAPPG 24-1 II.C.2.d.i.(b)
% "No more than six lines of text per vertical inch" - optimize spacing accordingly
\setlength{\parskip}{0pt plus 1pt}
\setlength{\parsep}{0pt}
\setlength{\itemsep}{0pt plus 1pt}

% Optimize section spacing for maximum content density
\titlespacing*{\section}{0pt}{6pt plus 2pt minus 2pt}{3pt plus 2pt minus 2pt}
\titlespacing*{\subsection}{0pt}{4pt plus 2pt minus 1pt}{2pt plus 1pt minus 1pt}
\titlespacing*{\subsubsection}{0pt}{3pt plus 1pt minus 1pt}{1pt plus 1pt minus 1pt}

% Optimize list spacing
\setlist[itemize]{nosep, leftmargin=*, topsep=2pt, partopsep=0pt}
\setlist[enumerate]{nosep, leftmargin=*, topsep=2pt, partopsep=0pt}
\setlist[description]{nosep, leftmargin=*, topsep=2pt, partopsep=0pt}

% Figure and table optimization
\setlength{\floatsep}{6pt plus 2pt minus 2pt}
\setlength{\textfloatsep}{8pt plus 2pt minus 4pt}
\setlength{\intextsep}{8pt plus 2pt minus 2pt}

% Equation spacing optimization
\AtBeginDocument{%
  \setlength{\abovedisplayskip}{6pt plus 2pt minus 4pt}%
  \setlength{\belowdisplayskip}{6pt plus 2pt minus 4pt}%
  \setlength{\abovedisplayshortskip}{3pt plus 1pt minus 2pt}%
  \setlength{\belowdisplayshortskip}{3pt plus 1pt minus 2pt}%
}

% Widow and orphan control
\widowpenalty=10000
\clubpenalty=10000
\raggedbottom

% Bibliography optimization - PAPPG 24-1 II.C.2.d.i.(a) allows smaller fonts for references
$if(reference_font_size)$
\renewcommand{\bibfont}{\fontsize{$reference_font_size$}{$reference_font_size$ * 1.2}\selectfont}
$endif$

% Enable hyphenation optimization
\hyphenpenalty=1000
\tolerance=2000
\emergencystretch=10pt

% Custom commands for space optimization
\newcommand{\tightsection}[1]{\vspace{-2pt}\section{#1}\vspace{-2pt}}
\newcommand{\tightsubsection}[1]{\vspace{-1pt}\subsection{#1}\vspace{-1pt}}

% Title formatting
$if(title)$
\title{\textbf{$title$}}
$endif$

$if(author)$
\author{$author$}
$endif$

$if(date)$
\date{$date$}
$else$
\date{}
$endif$

\begin{document}

$if(title)$
\maketitle
\vspace{-10pt}  % Reduce space after title
$endif$

$if(abstract)$
\begin{abstract}
$abstract$
\end{abstract}
\vspace{-5pt}
$endif$

$body$

$if(bibliography)$
\bibliographystyle{unsrt}
\bibliography{$bibliography$}
$endif$

\end{document}
"""
    
    def _get_standard_template(self) -> str:
        """Standard LaTeX template with NSF PAPPG 24-1 compliance."""
        return r"""
% NSF PAPPG 24-1 Compliant Standard Template
% References: https://www.nsf.gov/pubs/policydocs/pappguide/nsf24001/index.jsp

\documentclass[10pt]{article}  % PAPPG 24-1 II.C.2.d.i.(a): 10pt minimum font size

% Standard NSF-compliant packages
\usepackage[letterpaper, margin=1in]{geometry}  % PAPPG 24-1 II.C.2.d.i.(c): 1-inch margins
\usepackage{times}  % PAPPG 24-1 II.C.2.d.i.(a): Times New Roman or equivalent
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{setspace}
\usepackage{titlesec}
\usepackage{graphicx}
\usepackage{float}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{enumitem}
\usepackage{amsmath}
\usepackage{amsfonts}
\usepackage{url}
\usepackage[hidelinks]{hyperref}

% Font settings - PAPPG 24-1 II.C.2.d.i.(a)
\renewcommand{\normalsize}{\fontsize{10}{12}\selectfont}  % 10pt for maximum content

% Standard spacing
$if(line_spacing)$
$if(line_spacing == "single")$
\singlespacing
$elseif(line_spacing == "1.5")$
\onehalfspacing
$endif$
$else$
\singlespacing
$endif$

% Title
$if(title)$
\title{\textbf{$title$}}
$endif$

$if(author)$
\author{$author$}
$endif$

$if(date)$
\date{$date$}
$else$
\date{}
$endif$

\begin{document}

$if(title)$
\maketitle
$endif$

$if(abstract)$
\begin{abstract}
$abstract$
\end{abstract}
$endif$

$body$

$if(bibliography)$
\bibliographystyle{unsrt}
\bibliography{$bibliography$}
$endif$

\end{document}
"""
    
    def save_template(self, template_name: str, content: str) -> Path:
        """Save a template to the templates directory."""
        template_path = self.template_dir / f"{template_name}.tex"
        template_path.write_text(content, encoding='utf-8')
        return template_path
    
    def get_template_path(self, template_name: str) -> Optional[Path]:
        """Get path to a saved template."""
        template_path = self.template_dir / f"{template_name}.tex"
        return template_path if template_path.exists() else None
    
    def create_nsf_templates(self) -> Dict[str, Path]:
        """Create and save all NSF templates."""
        templates = {
            "nsf_optimized": self._get_space_optimized_template(),
            "nsf_standard": self._get_standard_template(),
        }
        
        paths = {}
        for name, content in templates.items():
            paths[name] = self.save_template(name, content)
            
        return paths
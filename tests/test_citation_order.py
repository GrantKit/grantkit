"""Citation numbering must be deterministic and shared across documents.

Regression tests for a submitted NSF proposal (Sept 2026) whose Summary and
References Cited were numbered in one Python process and whose Project
Description was numbered in another. The alphabetical sort keyed on the first
author's surname only, and its input came from ``list(set(keys))``, so entries
sharing a surname (several corporate authors ending in "Foundation", several
entries by one organization, several by its project "Team") kept a
hash-randomized order. 19 of the 48 numbers in the submitted Project
Description pointed at the wrong References Cited entries.

The fixture bibliography below reproduces that tie structure.
"""

import json
import os
import re
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

from grantkit.references import BibliographyGenerator, BibTeXManager
from grantkit.references.nsf_styles import NSFBibliographyFormatter

REPO_ROOT = Path(__file__).resolve().parent.parent

BIB = r"""
@misc{nsfSolicitation,
  author = {{National Science Foundation}},
  title = {Program Solicitation},
  year = {2026}
}
@misc{nsfWebinar,
  author = {{National Science Foundation}},
  title = {Program Webinar},
  year = {2026}
}
@misc{nsfAward,
  author = {{National Science Foundation}},
  title = {Award Abstract},
  year = {2025}
}
@misc{softwareFoundation,
  author = {{Public Software Foundation}},
  title = {Open Source Infrastructure for Public Policy},
  year = {2026}
}
@misc{rulesEngine,
  author = {{The Rules Foundation}},
  title = {Rules Engine},
  year = {2026}
}
@misc{openssf,
  author = {{Open Source Security Foundation}},
  title = {OpenSSF Scorecard},
  year = {2026}
}
@misc{labUS,
  author = {{Civic Models Lab}},
  title = {civic-models-us},
  year = {2026}
}
@misc{labUK,
  author = {{Civic Models Lab}},
  title = {civic-models-uk},
  year = {2026}
}
@misc{labCanada,
  author = {{Civic Models Lab}},
  title = {civic-models-canada},
  year = {2026}
}
@misc{labScorecard,
  author = {{Civic Models Lab}},
  title = {Civic Models Scorecard},
  year = {2026}
}
@misc{labAudit,
  author = {{Civic Models Lab}},
  title = {Repository Security Baseline},
  year = {2026}
}
@misc{bf,
  author = {{BenefitsFinder}},
  title = {About Us},
  year = {2025}
}
@misc{bfGrant,
  author = {{BenefitsFinder}},
  title = {Accelerating Benefits Access},
  year = {2024}
}
@misc{teamInterviews,
  author = {{Civic Models Lab Project Team}},
  title = {Interview Export},
  year = {2026}
}
@misc{teamKickoff,
  author = {{Civic Models Lab Project Team}},
  title = {Kickoff Calendar},
  year = {2026}
}
@misc{teamFinal,
  author = {{Civic Models Lab Project Team}},
  title = {Final Presentation},
  year = {2026}
}
@article{rivera2020,
  author = {Rivera, Ana and Smith, John},
  title = {Earlier Work},
  journal = {Journal of Examples},
  year = {2020}
}
@article{rivera2026,
  author = {Rivera, Tomas},
  title = {Letter of Collaboration},
  journal = {Journal of Examples},
  year = {2026}
}
@article{feenberg1993,
  author = {Feenberg, Daniel and Coutts, Elisabeth},
  title = {An Introduction to the TAXSIM Model},
  journal = {Journal of Policy Analysis and Management},
  year = {1993}
}
@misc{doeFirstLast,
  author = {Jane Doe},
  title = {First Last Format},
  year = {2021}
}
@misc{untitledData,
  title = {Untitled Dataset},
  year = {2020}
}
"""

ALL_KEYS = [
    "nsfSolicitation",
    "nsfWebinar",
    "nsfAward",
    "softwareFoundation",
    "rulesEngine",
    "openssf",
    "labUS",
    "labUK",
    "labCanada",
    "labScorecard",
    "labAudit",
    "bf",
    "bfGrant",
    "teamInterviews",
    "teamKickoff",
    "teamFinal",
    "rivera2020",
    "rivera2026",
    "feenberg1993",
    "doeFirstLast",
    "untitledData",
]

# First author's surname (corporate names whole), then the tie-break: full
# author list, year, title, key. Pinned so the order is a documented
# contract, not whatever the sort happens to do.
EXPECTED_ORDER = [
    "bfGrant",  # benefitsfinder, 2024
    "bf",  # benefitsfinder, 2025
    "labScorecard",  # civic models lab, 2026, "civic models scorecard"
    "labCanada",  # ... "civic-models-canada" (" " < "-")
    "labUK",
    "labUS",
    "labAudit",  # ... "repository..."
    "teamFinal",  # civic models lab project team, "final..."
    "teamInterviews",
    "teamKickoff",
    "doeFirstLast",  # doe
    "feenberg1993",  # feenberg
    "nsfAward",  # national science foundation, 2025
    "nsfSolicitation",  # ... 2026, "program solicitation"
    "nsfWebinar",  # ... 2026, "program webinar"
    "openssf",  # open source security foundation
    "softwareFoundation",  # public software foundation
    "rivera2020",  # rivera, ana
    "rivera2026",  # rivera, tomas
    "rulesEngine",  # the rules foundation
    "untitledData",  # no author: sorted by key
]

# One key per line as "<key>: [@<key>]", so the numbered text reads
# "<key>: [n]" and the key→number map can be read back unambiguously.
SUMMARY_KEYS = ["labUS", "nsfSolicitation", "bf", "teamFinal", "rivera2026"]
DESCRIPTION_KEYS = ALL_KEYS  # the description cites everything
SUMMARY = "\n".join(f"{key}: [@{key}]" for key in SUMMARY_KEYS) + (
    "\ngroup: [@labUK; @nsfWebinar]\n"
)
DESCRIPTION = "\n".join(f"{key}: [@{key}]" for key in DESCRIPTION_KEYS) + (
    "\ngroup: [@teamKickoff; @labAudit; @bfGrant]\n"
)

LINE = re.compile(r"^(\w+): \[(\d+)\]$", re.MULTILINE)


def numbers_by_key(numbered: str) -> dict[str, int]:
    return {key: int(n) for key, n in LINE.findall(numbered)}


@pytest.fixture
def bib_root(tmp_path: Path) -> Path:
    (tmp_path / "references.bib").write_text(BIB, encoding="utf-8")
    return tmp_path


@pytest.fixture
def generator(bib_root: Path) -> BibliographyGenerator:
    return BibliographyGenerator(bib_root)


def run_with_hash_seeds(
    runs: list[tuple[str, tuple[str, ...]]], script: str
) -> list[object]:
    """Run ``script`` once per ``(seed, args)``, each in a fresh interpreter
    under ``PYTHONHASHSEED=seed``, concurrently.

    Each run prints one JSON document; return them parsed, in order.
    """
    procs = []
    for seed, args in runs:
        env = dict(os.environ, PYTHONHASHSEED=seed)
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(REPO_ROOT), env.get("PYTHONPATH")])
        )
        procs.append(
            subprocess.Popen(
                [sys.executable, "-c", script, *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
        )
    results = []
    for (seed, _), proc in zip(runs, procs):
        stdout, stderr = proc.communicate(timeout=120)
        assert proc.returncode == 0, f"PYTHONHASHSEED={seed}: {stderr}"
        results.append(json.loads(stdout))
    return results


HASH_SEEDS = ["0", "1", "2", "3", "4", "5", "6", "7", "42", "12345"]


# -- (a) same-surname ties: identical order under every hash seed --------

ORDER_SCRIPT = """
import json, sys
from pathlib import Path
from grantkit.references import BibliographyGenerator

root, summary, description = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
gen = BibliographyGenerator(root)
gen.bibtex_manager.load_bibliography()
keys = list(gen.bibtex_manager.entries)
numbered, own_order = gen.process_content_with_citations(description)
refs = gen.create_separate_references_document(description)
print(json.dumps({
    # What the Sept 2026 driver did: sort a set's (hash-ordered) keys.
    "sort_of_set": gen._sort_citations(list(set(keys))),
    "own_order": own_order,
    "numbered": numbered,
    "references": refs.bibliography_content,
    "union_order": gen.citation_order([summary, description]),
}))
"""


def test_tie_order_is_identical_under_every_hash_seed(bib_root):
    args = (str(bib_root), SUMMARY, DESCRIPTION)
    results = run_with_hash_seeds(
        [(seed, args) for seed in HASH_SEEDS], ORDER_SCRIPT
    )
    first = results[0]
    for seed, result in zip(HASH_SEEDS, results):
        assert result == first, f"PYTHONHASHSEED={seed} changed the output"
    assert first["sort_of_set"] == EXPECTED_ORDER
    assert first["own_order"] == EXPECTED_ORDER
    assert first["union_order"] == EXPECTED_ORDER


def test_fixture_has_surname_ties_the_old_key_left_unbroken(generator):
    """Guard the test's power: the fixture must contain real tie blocks.

    Under the pre-fix key (first word-split surname only) these entries
    compared equal, which is what let set order leak into numbering.
    """
    generator.bibtex_manager.load_bibliography()

    def old_key(key: str) -> str:
        entry = generator.bibtex_manager.get_entry(key)
        if entry and entry.authors:
            first = entry.authors[0]
            if "," in first:
                return first.split(",")[0].strip().lower()
            return first.split()[-1].lower()
        return key.lower()

    blocks: dict[str, list[str]] = {}
    for key in ALL_KEYS:
        blocks.setdefault(old_key(key), []).append(key)
    sizes = sorted(len(v) for v in blocks.values() if len(v) > 1)
    # foundation x6, lab x5, team x3, rivera x2, benefitsfinder x2
    assert sizes == [2, 2, 3, 5, 6]


def test_expected_order_in_process(generator):
    order = generator.citation_order([DESCRIPTION])
    assert order == EXPECTED_ORDER
    # Input order must not matter.
    assert generator._sort_citations(reversed(ALL_KEYS)) == EXPECTED_ORDER
    assert generator._sort_citations(sorted(ALL_KEYS)) == EXPECTED_ORDER


def test_sort_drops_duplicates_keeping_one(generator):
    generator.bibtex_manager.load_bibliography()
    assert generator._sort_citations(["labUS", "labUK", "labUS"]) == [
        "labUK",
        "labUS",
    ]


# -- (b) summary and description agree on every shared key's number -----


def assert_consistent(summary_numbered, description_numbered, order):
    summary_numbers = numbers_by_key(summary_numbered)
    description_numbers = numbers_by_key(description_numbered)
    assert set(summary_numbers) == set(SUMMARY_KEYS)
    assert set(description_numbers) == set(DESCRIPTION_KEYS)
    for key in SUMMARY_KEYS:
        assert summary_numbers[key] == description_numbers[key], key
        # And [n] resolves to order[n - 1], the References Cited entry.
        assert order[summary_numbers[key] - 1] == key


def test_summary_and_description_numbered_separately_agree(generator):
    order = generator.citation_order([SUMMARY, DESCRIPTION])
    summary, _ = generator.process_content_with_citations(
        SUMMARY, citation_order=order
    )
    description, _ = generator.process_content_with_citations(
        DESCRIPTION, citation_order=order
    )
    assert_consistent(summary, description, order)

    n = {key: i for i, key in enumerate(order, 1)}
    assert f"group: [{n['labUK']}, {n['nsfWebinar']}]" in summary
    assert (
        f"group: [{n['teamKickoff']}, {n['labAudit']}, {n['bfGrant']}]"
        in description
    )


def test_process_documents_with_citations(generator):
    (summary, description), order = generator.process_documents_with_citations(
        [SUMMARY, DESCRIPTION]
    )
    assert order == generator.citation_order([SUMMARY, DESCRIPTION])
    assert_consistent(summary, description, order)


NUMBER_SCRIPT = """
import json, sys
from pathlib import Path
from grantkit.references import BibliographyGenerator

root, which, summary, description = (
    Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
)
gen = BibliographyGenerator(root)
# Each process builds the shared order itself, as a real build driver
# would, then numbers only its own document.
order = gen.citation_order([summary, description])
if which == "references":
    result = gen.create_separate_references_document(
        summary + "\\n" + description, citation_order=order
    )
    print(json.dumps({"order": order, "text": result.bibliography_content}))
else:
    text = summary if which == "summary" else description
    numbered, _ = gen.process_content_with_citations(text, citation_order=order)
    print(json.dumps({"order": order, "text": numbered}))
"""


def test_documents_numbered_in_separate_processes_agree(bib_root):
    """The Sept 2026 failure mode: one process per document, any seed."""
    root = str(bib_root)
    summary, description, references = run_with_hash_seeds(
        [
            ("1", (root, "summary", SUMMARY, DESCRIPTION)),
            ("2", (root, "description", SUMMARY, DESCRIPTION)),
            ("3", (root, "references", SUMMARY, DESCRIPTION)),
        ],
        NUMBER_SCRIPT,
    )
    order = summary["order"]
    assert description["order"] == order == references["order"]
    assert_consistent(summary["text"], description["text"], order)

    # References Cited, numbered in a third process, lists at [n] the
    # entry that both documents print as [n].
    entries = {
        int(n): line
        for n, line in re.findall(
            r"^\[(\d+)\] (.*)$", references["text"], re.MULTILINE
        )
    }
    bib = BibTeXManager(bib_root)
    bib.load_bibliography()
    for key, n in numbers_by_key(description["text"]).items():
        title = bib.get_entry(key).title
        assert f'"{title}."' in entries[n], (key, n, entries[n])


def test_single_document_numbering_is_local(generator):
    """Numbering a document alone uses only its keys, so it diverges.

    This is why the shared-order API exists; the docstrings say so, and
    this pins it.
    """
    alone, _ = generator.process_content_with_citations(SUMMARY)
    order = generator.citation_order([SUMMARY, DESCRIPTION])
    shared, _ = generator.process_content_with_citations(
        SUMMARY, citation_order=order
    )
    assert numbers_by_key(alone) != numbers_by_key(shared)


def test_key_missing_from_shared_order_raises(generator):
    order = generator.citation_order([SUMMARY])
    with pytest.raises(ValueError, match="feenberg1993"):
        generator.process_content_with_citations(
            DESCRIPTION, citation_order=order
        )
    # This one reports errors in its result rather than raising.
    result = generator.create_separate_references_document(
        DESCRIPTION, citation_order=order
    )
    assert not result.success
    assert "feenberg1993" in result.errors[0]


def test_citation_order_accepts_a_bare_string(generator):
    assert generator.citation_order(SUMMARY) == generator.citation_order(
        [SUMMARY]
    )


def test_numbering_loads_the_bibliography_itself(bib_root):
    """Without the .bib loaded, keys would sort by their own names.

    The legacy PDF pipeline numbered the text before anything had loaded
    the .bib, so text (key order) and References Cited (author order)
    disagreed.
    """
    fresh = BibliographyGenerator(bib_root)
    _, order = fresh.process_content_with_citations(DESCRIPTION)
    assert order == EXPECTED_ORDER


def test_missing_key_keeps_its_number_in_references(generator):
    text = "a [@nsfSolicitation] b [@notInBib] c [@rivera2026]"
    numbered, order = generator.process_content_with_citations(text)
    assert order == ["nsfSolicitation", "notInBib", "rivera2026"]
    assert numbered == "a [1] b [2] c [3]"

    result = generator.create_separate_references_document(text)
    assert not result.success
    assert "Citation key 'notInBib' not found in bibliography" in (
        result.errors
    )
    assert result.citation_order == order
    assert "[2] **Missing entry: notInBib**" in result.bibliography_content
    assert "[3] Rivera, Tomas." in result.bibliography_content

    section = generator.generate_references_section(order)
    assert "[2] **Missing entry: notInBib**" in section
    assert "[3] Rivera, Tomas." in section


# -- corporate authors ---------------------------------------------------


def test_corporate_authors_are_flagged(generator):
    generator.bibtex_manager.load_bibliography()
    nsf = generator.bibtex_manager.get_entry("nsfSolicitation")
    assert nsf.authors == ["National Science Foundation"]
    assert nsf.corporate_authors == ["National Science Foundation"]
    person = generator.bibtex_manager.get_entry("rivera2020")
    assert person.corporate_authors == []


def test_corporate_author_is_not_inverted_in_references(generator):
    text = "[@nsfSolicitation] [@teamFinal] [@rivera2026] [@doeFirstLast]"
    content = generator.create_separate_references_document(
        text
    ).bibliography_content
    # Sorted civic models lab project team < doe < national science
    # foundation < rivera: the corporate names sort (and print) whole.
    assert "[1] Civic Models Lab Project Team." in content
    assert "[3] National Science Foundation." in content
    assert "Foundation, National Science" not in content
    assert "Team, Civic Models Lab Project" not in content
    # People are still inverted.
    assert "[2] Doe, Jane." in content
    assert "[4] Rivera, Tomas." in content


def test_mixed_corporate_and_person_authors(tmp_path):
    (tmp_path / "references.bib").write_text(
        r"""
@misc{mou,
  author = {{World Health Organization} and {Civic Models Lab}
            and Smith, John},
  title = {Memorandum of Understanding},
  year = {2026}
}
""",
        encoding="utf-8",
    )
    manager = BibTeXManager(tmp_path)
    manager.load_bibliography()
    entry = manager.get_entry("mou")
    assert entry.authors == [
        "World Health Organization",
        "Civic Models Lab",
        "Smith, John",
    ]
    assert entry.corporate_authors == [
        "World Health Organization",
        "Civic Models Lab",
    ]
    formatted = NSFBibliographyFormatter().format_entry(entry, 1)
    assert formatted.startswith(
        "[1] World Health Organization, Civic Models Lab, and Smith, John."
    )


def test_and_separator_may_span_lines(tmp_path):
    """BibTeX splits names on "and" with any surrounding whitespace."""
    (tmp_path / "references.bib").write_text(
        """
@article{rda,
  author = {Hanisch, Robert J. and Kaiser, Debra L. and
            Yuan, Alda and {Research Data
            Alliance}},
  title = {Framework},
  year = {2024}
}
""",
        encoding="utf-8",
    )
    manager = BibTeXManager(tmp_path)
    manager.load_bibliography()
    entry = manager.get_entry("rda")
    assert entry.authors == [
        "Hanisch, Robert J.",
        "Kaiser, Debra L.",
        "Yuan, Alda",
        "Research Data Alliance",
    ]
    assert entry.corporate_authors == ["Research Data Alliance"]


def test_braced_name_parts_are_a_person_not_an_institution(tmp_path):
    """``{Eric} {Smith}`` protects capitalization; it is two groups."""
    (tmp_path / "references.bib").write_text(
        "@misc{es, author = {{Eric} {Smith}}, title = {T}, year = {2020}}\n",
        encoding="utf-8",
    )
    manager = BibTeXManager(tmp_path)
    manager.load_bibliography()
    entry = manager.get_entry("es")
    assert entry.authors == ["Eric Smith"]
    assert entry.corporate_authors == []
    assert (
        NSFBibliographyFormatter()
        .format_entry(entry, 1)
        .startswith("[1] Smith, Eric.")
    )


def test_single_braced_name_is_still_split_as_a_person(tmp_path):
    """Single braces are ordinary BibTeX name syntax; double braces protect.

    (The docs tell users to write ``{{National Science Foundation}}``.)
    """
    (tmp_path / "references.bib").write_text(
        "@misc{n, author = {National Science Foundation}, title = {T}}\n",
        encoding="utf-8",
    )
    manager = BibTeXManager(tmp_path)
    manager.load_bibliography()
    assert manager.get_entry("n").corporate_authors == []


# -- .bib discovery and loading ------------------------------------------

DISCOVERY_SCRIPT = """
import json, sys
from pathlib import Path
from grantkit.references import BibTeXManager

manager = BibTeXManager(Path(sys.argv[1]))
manager.load_bibliography()
manager.load_bibliography()  # a reload must not change the winner
print(json.dumps({
    "files": [str(p) for p in manager.bibtex_files],
    "title": manager.get_entry("dup").title,
}))
"""


@pytest.fixture
def duplicate_key_root(tmp_path: Path) -> Path:
    """Six .bib files across the search paths, all defining ``dup``."""
    locations = {
        "": ["b.bib", "a.bib"],
        "references": ["z.bib", "m.bib"],
        "docs": ["c.bib"],
        "sections": ["d.bib"],
    }
    for sub, names in locations.items():
        folder = tmp_path / sub
        folder.mkdir(exist_ok=True)
        for name in names:
            (folder / name).write_text(
                f"@misc{{dup, title = {{{sub or 'root'}/{name}}}}}\n",
                encoding="utf-8",
            )
    return tmp_path


def test_bib_files_load_in_a_fixed_order(duplicate_key_root):
    root = duplicate_key_root
    manager = BibTeXManager(root)
    assert manager.bibtex_files == [
        root / "a.bib",
        root / "b.bib",
        root / "references" / "m.bib",
        root / "references" / "z.bib",
        root / "docs" / "c.bib",
        root / "sections" / "d.bib",
    ]
    manager.load_bibliography()
    assert manager.get_entry("dup").title == "sections/d.bib"


def test_duplicate_key_winner_is_the_same_under_every_hash_seed(
    duplicate_key_root,
):
    args = (str(duplicate_key_root),)
    results = run_with_hash_seeds(
        [(seed, args) for seed in HASH_SEEDS], DISCOVERY_SCRIPT
    )
    assert all(result == results[0] for result in results)
    assert results[0]["title"] == "sections/d.bib"


def test_reloading_reuses_no_parser_state(duplicate_key_root):
    """A reused bibtexparser parser returns every earlier parse again with
    each new file, and warns on its second use (every reload hit it)."""
    manager = BibTeXManager(duplicate_key_root)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        manager.load_bibliography()
        manager.load_bibliography()
    assert not [w for w in caught if "more than once" in str(w.message)]
    assert manager.get_entry("dup").title == "sections/d.bib"


def test_every_bib_file_loads_under_warnings_as_errors(tmp_path):
    """With the parser reused, the second file's parse raised that warning;
    under warnings-as-errors load_bibliography logged and swallowed it, so
    that file's entries silently went missing (which file depended on the
    hash seed)."""
    (tmp_path / "a.bib").write_text("@misc{a, title = {A}}\n")
    (tmp_path / "b.bib").write_text("@misc{b, title = {B}}\n")
    manager = BibTeXManager(tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        manager.load_bibliography()
    assert set(manager.entries) == {"a", "b"}


# -- legacy PDF pipeline -------------------------------------------------


def test_separated_pdfs_get_a_populated_references_document(
    bib_root, monkeypatch, tmp_path
):
    """generate_separated_pdfs built References Cited from numbered text.

    The numbered text has no ``[@key]`` left, so the list came out empty.
    """
    from grantkit.pdf.generator import PDFGenerationResult, PDFGenerator

    rendered: dict[str, str] = {}

    def fake_generate_pdf(self, markdown_content, output_path, **kwargs):
        rendered[output_path.name] = markdown_content
        return PDFGenerationResult(
            success=True,
            output_path=output_path,
            page_count=1,
            file_size_mb=0.0,
            generation_time_seconds=0.0,
            validation_result=None,
            optimization_suggestions=[],
            errors=[],
            warnings=[],
        )

    monkeypatch.setattr(PDFGenerator, "generate_pdf", fake_generate_pdf)
    generator = PDFGenerator(project_root=bib_root)
    result = generator.generate_separated_pdfs(
        DESCRIPTION, tmp_path / "main.pdf", validate=False, optimize=False
    )
    assert result.success, result.errors
    main = rendered["main.pdf"]
    references = rendered["main_references.pdf"]
    assert "No references found" not in references
    numbers = numbers_by_key(main)
    bib = BibTeXManager(bib_root)
    bib.load_bibliography()
    for key in ("nsfSolicitation", "labUS", "teamFinal", "rivera2020"):
        title = bib.get_entry(key).title
        assert f"[{numbers[key]}] " in references
        line = next(
            line
            for line in references.splitlines()
            if line.startswith(f"[{numbers[key]}] ")
        )
        assert f'"{title}."' in line, (key, line)

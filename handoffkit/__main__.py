import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict

def approx_tokens(text: str) -> int:
    # Extremely rough heuristic: ~4 chars/token typical for English.
    return max(1, len(text) // 4)

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="replace")

def strip_frontmatter(md: str) -> str:
    # Strips simple YAML frontmatter if present: --- ... --- at the top.
    if md.startswith("---"):
        parts = md.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip("\n")
    return md

def resolve_path(path_str: str, project_root: Path) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = (project_root / p).resolve()
    return p

def read_artifact_file(path_str: Optional[str], *, project_root: Path, label: str, required: bool) -> Tuple[Optional[str], Optional[Path]]:
    if not path_str:
        if required:
            raise FileNotFoundError(f"{label} file not specified.")
        return None, None
    p = resolve_path(path_str, project_root)
    if not p.exists():
        if required:
            raise FileNotFoundError(f"{label} file not found: {p}")
        return None, None
    content = read_text(p).strip()
    if not content:
        if required:
            raise RuntimeError(f"{label} file is empty: {p}")
        return None, p
    return content, p

def find_project_root(start: Path) -> Path:
    """Walk upwards to find a likely project root (Local MCP layout)."""
    start = start.resolve()
    for p in [start] + list(start.parents):
        if (p / "docs" / "PROJECT_CONTEXT.md").exists():
            return p
        if (p / ".git").exists():
            # If we're in a git repo but no docs found, still treat repo root as root.
            return p
    return start

def extract_summary_block(text: str) -> Optional[str]:
    s = text.find("<!-- SUMMARY_START -->")
    e = text.find("<!-- SUMMARY_END -->")
    if s != -1 and e != -1 and e > s:
        return text[s + len("<!-- SUMMARY_START -->"):e].strip()
    return None

def tail_lines(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    return "\n".join(lines[-max_lines:]).strip()

def truncate_text(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    limit = max_tokens * 4
    if len(text) <= limit:
        return text.strip()
    truncated = False
    cut = text.rfind("\n", 0, limit)
    if cut == -1:
        cut = limit
    truncated = True
    out = (text[:cut].rstrip() + "\n…(truncated)…").strip()
    if truncated and out.count("```") % 2 == 1:
        out = out.rstrip() + "\n```"
    return out.strip()

ROLE_CHOICES = ["architect", "coder", "reviewer", "qa_tester", "polish", "qa"]
SESSION_ROLE_CHOICES = ["Architect", "Coder", "Reviewer", "QA"]

def resolve_role_prompt_file(project_root: Path, tool_root: Path, role: str) -> Optional[Path]:
    """Resolve prompt file path with repo override and template fallback."""
    role = role.lower()
    slug_candidates = [role]
    if role == "qa_tester":
        slug_candidates = ["qa_tester", "qa"]
    elif role == "qa":
        slug_candidates = ["qa", "qa_tester"]

    for slug in slug_candidates:
        repo_agent_path = project_root / ".github" / "agents" / f"{slug}.agent.md"
        if repo_agent_path.exists():
            return repo_agent_path

    for slug in slug_candidates:
        template_path = tool_root / "templates" / f"{slug}.md"
        if template_path.exists():
            return template_path

    return None

def display_path_for_prompt(path: Path, project_root: Path) -> str:
    """Render project-relative path when possible, absolute otherwise."""
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()

def read_optional_input(path_str: Optional[str], *, project_root: Path, label: str) -> Optional[str]:
    """Read optional content from a file path or stdin.

    Supports:
      --diff /path/to/file.diff
      --diff -    (read from stdin)
    Paths are resolved relative to project_root if not absolute.
    """
    if not path_str:
        return None
    if path_str == "-":
        data = sys.stdin.read()
        return f"## {label}\n\n```\n{data.strip()}\n```" if data.strip() else None
    p = Path(path_str)
    if not p.is_absolute():
        p = (project_root / p).resolve()
    if not p.exists():
        raise FileNotFoundError(f"{label} file not found: {p}")
    content = read_text(p).strip()
    if not content:
        return None
    return f"## {label}\n\n```\n{content}\n```"

def load_config(project_root: Path, tool_root: Path, config_path: Optional[str]) -> Dict:
    """Load config.

    Search order (unless explicit path provided):
      1) explicit --config
      2) <project_root>/handoffkit.config.json
      3) <tool_root>/handoffkit.config.json
    """
    candidates: List[Path] = []
    if config_path:
        p = Path(config_path)
        if not p.is_absolute():
            # allow relative to cwd
            p = (Path.cwd() / p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        candidates.append(p)
    else:
        candidates.append(project_root / "handoffkit.config.json")
        candidates.append(tool_root / "handoffkit.config.json")

    cfg_path = next((p for p in candidates if p.exists()), None)
    if cfg_path:
        try:
            return json.loads(read_text(cfg_path))
        except Exception as e:
            raise RuntimeError(f"Failed to parse config at {cfg_path}: {e}")

    # Defaults aligned to local-mcp-context-kit layout
    return {
        "token_budget": 2200,
        "baseline_files": [
            "docs/PROJECT_CONTEXT.md",
            "docs/NOW.md",
        ],
        "session_notes_file": "docs/SESSION_NOTES.md",
        "session_notes_tail_lines": 80,
        "protocol_file": "docs/AGENT_SESSION_PROTOCOL.md",
        "protocol_tail_lines": 120,
        "spec_file": "SPEC.md",
        "invariants_file": "docs/INVARIANTS.md",
        "require_spec": False,
        "require_invariants": False,
        "auto_include_spec": True,
        "auto_include_invariants": True,
    }

def load_role_prompt(project_root: Path, tool_root: Path, role: str) -> Tuple[str, Optional[Path]]:
    """Load role prompt from repo agents if present, else from kit templates."""
    prompt_path = resolve_role_prompt_file(project_root, tool_root, role)
    if prompt_path is None:
        raise FileNotFoundError(f"No prompt file found for role '{role}'")

    if prompt_path.name.endswith(".agent.md"):
        content = strip_frontmatter(read_text(prompt_path)).strip()
        return content, prompt_path
    return read_text(prompt_path).strip(), None

def read_baseline_section(project_root: Path, rel: str, max_tokens: int) -> Optional[Tuple[str,str]]:
    p = Path(rel)
    if not p.is_absolute():
        p = (project_root / p)
    if not p.exists():
        return None
    raw = read_text(p)
    summary = extract_summary_block(raw)
    content = summary if summary else raw.strip()
    # token cap
    if approx_tokens(content) > max_tokens:
        content = truncate_text(content, max_tokens)
    title = rel
    return title, content

def build_context_pack(
    project_root: Path,
    cfg: Dict,
    instruction: str,
    selection: Optional[str],
    diff_text: Optional[str],
    *,
    role_name: str,
    role_agent_path: Optional[Path],
    spec_content: Optional[str],
    spec_title: Optional[str],
    invariants_content: Optional[str],
    invariants_title: Optional[str],
) -> str:
    budget = int(cfg.get("token_budget", 2200))

    # High-priority sections (never trimmed too aggressively)
    header_lines = []
    header_lines.append("SESSION START – PROJECT CONTEXT")
    header_lines.append("")
    header_lines.append("You are a local code assistant working on this project.")
    header_lines.append("")
    if role_agent_path:
        header_lines.append(f"Role reference file: {role_agent_path.as_posix()}")
    header = "\n".join(header_lines).strip()

    sections: List[Tuple[str, str, int]] = []  # (title, content, priority)
    # priority: higher = keep more
    sections.append(("Instruction", instruction.strip(), 100))
    if spec_content:
        sections.append((spec_title or "SPEC.md", spec_content.strip(), 95))
    if invariants_content:
        sections.append((invariants_title or "Invariants", invariants_content.strip(), 95))
    if selection:
        sections.append(("Selection", selection, 90))
    if diff_text:
        sections.append(("Diff", diff_text, 90))

    # Baseline in priority order: NOW > PROJECT_CONTEXT
    for rel in cfg.get("baseline_files", []):
        if rel.endswith("NOW.md"):
            sections.append(("NOW", rel, 60))
        else:
            sections.append(("PROJECT_CONTEXT", rel, 50))

    # Session notes (tail)
    sn_rel = cfg.get("session_notes_file")
    if sn_rel:
        sn_path = project_root / sn_rel
        if sn_path.exists():
            sn_raw = read_text(sn_path)
            sn_summary = extract_summary_block(sn_raw)
            sn = sn_summary if sn_summary else tail_lines(sn_raw, int(cfg.get("session_notes_tail_lines", 80)))
            sections.append(("Recent SESSION_NOTES", sn, 35))

    # Protocol excerpt (tail)
    proto_rel = cfg.get("protocol_file")
    if proto_rel:
        proto_path = project_root / proto_rel
        if proto_path.exists():
            proto_raw = read_text(proto_path)
            proto_summary = extract_summary_block(proto_raw)
            proto = proto_summary if proto_summary else tail_lines(proto_raw, int(cfg.get("protocol_tail_lines", 120)))
            sections.append(("AGENT_SESSION_PROTOCOL", proto, 25))

    # Materialize baseline file sections (which are stored as rel paths above)
    materialized: List[Tuple[str, str, int]] = []
    for title, content, prio in sections:
        if title in ("NOW", "PROJECT_CONTEXT") and isinstance(content, str):
            max_tok = 450 if title == "NOW" else 650
            rb = read_baseline_section(project_root, content, max_tokens=max_tok)
            if rb:
                t, c = rb
                materialized.append((t, c, prio))
                continue
        materialized.append((title, content, prio))

    # Budgeting: allocate more to higher priority, but keep everything if possible.
    # We'll trim lower-priority sections first.
    def section_tokens(txt: str) -> int:
        stripped = txt.strip()
        if not stripped:
            return 0
        return approx_tokens(stripped)

    # Prepare pretty formatting
    out_parts = [header, ""]
    # Reserve a small amount for framing + markdown overhead.
    reserved = min(120, max(40, budget // 5))
    remaining = max(0, budget - reserved)

    # Sort by priority desc for initial inclusion, but we'll render in a logical order later.
    # First, trim if needed.
    mats = materialized[:]
    total = sum(section_tokens(c) for _, c, _ in mats)
    if total > remaining:
        # Trim in ascending priority order.
        mats_sorted = sorted(mats, key=lambda x: x[2])
        over = total - remaining
        trimmed = []
        for title, content, prio in mats_sorted:
            if over <= 0:
                trimmed.append((title, content, prio))
                continue
            min_keep = 160 if prio >= 90 else 120 if prio >= 60 else 90 if prio >= 35 else 60
            tok = section_tokens(content)
            if tok <= min_keep:
                trimmed.append((title, content, prio))
                continue
            cut = min(tok - min_keep, over)
            new_tok = tok - cut
            new_content = truncate_text(content, new_tok)
            trimmed.append((title, new_content, prio))
            over -= cut
        mats = trimmed

    over = sum(section_tokens(c) for _, c, _ in mats) - remaining
    if over > 0:
        # If we still exceed the budget, trim below the soft minimum.
        mats_sorted = sorted(mats, key=lambda x: x[2])
        trimmed = []
        for title, content, prio in mats_sorted:
            if over <= 0:
                trimmed.append((title, content, prio))
                continue
            hard_min = 80 if prio >= 90 else 60 if prio >= 60 else 40 if prio >= 35 else 20
            tok = section_tokens(content)
            if tok <= hard_min:
                trimmed.append((title, content, prio))
                continue
            cut = min(tok - hard_min, over)
            new_tok = tok - cut
            new_content = truncate_text(content, new_tok)
            trimmed.append((title, new_content, prio))
            over -= cut
        mats = trimmed

    over = sum(section_tokens(c) for _, c, _ in mats) - remaining
    if over > 0:
        # Final pass: trim lowest priority sections further to guarantee the cap.
        mats_sorted = sorted(mats, key=lambda x: x[2])
        trimmed = []
        for title, content, prio in mats_sorted:
            if over <= 0:
                trimmed.append((title, content, prio))
                continue
            tok = section_tokens(content)
            if tok <= 0:
                trimmed.append((title, content, prio))
                continue
            cut = min(tok, over)
            new_tok = tok - cut
            new_content = truncate_text(content, new_tok)
            trimmed.append((title, new_content, prio))
            over -= cut
        mats = trimmed

    # Render in deterministic order:
    render_order = ["Instruction"]
    if invariants_content:
        render_order.append(invariants_title or "Invariants")
    if spec_content:
        render_order.append(spec_title or "SPEC.md")
    render_order.extend(["docs/NOW.md", "docs/PROJECT_CONTEXT.md", "Recent SESSION_NOTES", "AGENT_SESSION_PROTOCOL", "Selection", "Diff"])
    # Map titles
    rendered = []
    for wanted in render_order:
        for title, content, prio in mats:
            if title == wanted:
                rendered.append((title, content))
    # Also include any leftovers
    existing_titles = {t for t,_ in rendered}
    for title, content, _ in mats:
        if title not in existing_titles:
            rendered.append((title, content))

    for title, content in rendered:
        if title == "Instruction":
            out_parts.append("## Instruction")
            out_parts.append(content.strip())
            out_parts.append("")
        elif title in ("Selection", "Diff"):
            # already includes markdown header/fence
            out_parts.append(content.strip())
            out_parts.append("")
        else:
            out_parts.append(f"## {title}")
            out_parts.append(content.strip())
            out_parts.append("")

    out_parts.append("SESSION END – INSTRUCTIONS")
    out_parts.append("")
    out_parts.append("When you finish your response, include a short section titled 'Session Updates' with:")
    out_parts.append("- 2–5 bullets summarizing what we did")
    out_parts.append("- Any updates needed for docs/NOW.md and docs/SESSION_NOTES.md (per AGENT_SESSION_PROTOCOL)")
    out_parts.append("- Next actions (if any)")
    return "\n".join(out_parts).strip()

def run_git(args: List[str], *, cwd: Path, capture: bool = False, check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            capture_output=capture,
            check=False,
        )
    except FileNotFoundError:
        if check:
            raise RuntimeError("git not found on PATH")
        return ""
    if check and result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {details}")
    return result.stdout if capture else ""

def preflight_report(project_root: Path, cfg: Dict) -> int:
    print("Local MCP – Preflight")
    print("")

    issues = 0

    def check_file(label: str, path_str: Optional[str], *, required: bool) -> None:
        nonlocal issues
        if not path_str:
            if required:
                print(f"MISSING: {label} (no path configured)")
                issues += 1
            else:
                print(f"SKIP: {label} (no path configured)")
            return
        p = resolve_path(path_str, project_root)
        if not p.exists():
            if required:
                print(f"MISSING: {label} ({p.as_posix()})")
                issues += 1
            else:
                print(f"WARN: {label} not found ({p.as_posix()})")
            return
        content = read_text(p).strip()
        if not content and required:
            print(f"MISSING: {label} is empty ({p.as_posix()})")
            issues += 1
        else:
            print(f"OK: {label} ({p.as_posix()})")
        if extract_summary_block(content) is None:
            print(f"INFO: {label} has no SUMMARY block")

    for rel in cfg.get("baseline_files", []):
        check_file(rel, rel, required=True)

    check_file("Session notes", cfg.get("session_notes_file"), required=True)
    check_file("Protocol", cfg.get("protocol_file"), required=True)

    auto_spec = bool(cfg.get("auto_include_spec", True))
    auto_invariants = bool(cfg.get("auto_include_invariants", True))
    require_spec = bool(cfg.get("require_spec", False))
    require_invariants = bool(cfg.get("require_invariants", False))

    if auto_spec or require_spec:
        check_file("SPEC.md", cfg.get("spec_file"), required=require_spec)
    if auto_invariants or require_invariants:
        check_file("Invariants", cfg.get("invariants_file"), required=require_invariants)

    if issues:
        print("")
        print(f"Preflight failed with {issues} issue(s).")
    else:
        print("")
        print("Preflight OK.")
    return 1 if issues else 0

def current_branch(project_root: Path) -> str:
    try:
        return run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root, capture=True).strip()
    except RuntimeError:
        return ""

def print_session_start(project_root: Path, tool_root: Path, agent_role: str, open_docs: bool) -> None:
    agent_role_slug = agent_role.lower()
    default_agent_role_file = f".github/agents/{agent_role_slug}.agent.md"
    role_prompt_path = resolve_role_prompt_file(project_root, tool_root, agent_role)
    if role_prompt_path is None:
        agent_role_file = default_agent_role_file
        role_prompt_warning = (
            f"WARNING: No role prompt file found for '{agent_role}'. "
            f"Expected repo file '{default_agent_role_file}' or template fallback."
        )
    else:
        agent_role_file = display_path_for_prompt(role_prompt_path, project_root)
        role_prompt_warning = None

    print("Local MCP – Start Session")
    print("")
    branch = current_branch(project_root)
    if branch:
        print(f"Current Git branch: {branch}")
        print("")

    print("SESSION START")
    print("")
    print("Paste the block below into your local code agent (e.g. VS Code Code Agent).")
    print("")
    if role_prompt_warning:
        print(role_prompt_warning)
        print("")
    lines = [
        "SESSION START – PROJECT CONTEXT",
        "",
        "You are a local code assistant working on this project.",
        "",
        "Before doing anything:",
        "",
        "0. Assume the role described here:",
        f"   - {agent_role_file}",
        "",
        "1. Read these files in this order:",
        "   - docs/PROJECT_CONTEXT.md",
        "   - docs/NOW.md",
        "   - docs/SESSION_NOTES.md",
        "",
        "2. Summarise the current context in 3–6 bullet points so we both know you understood it.",
        "",
        "3. Then wait for my next instruction.",
    ]
    print("\n".join(lines))

    if open_docs:
        print("")
        code_exe = shutil.which("code")
        if code_exe:
            print("Opening docs in VS Code...")
            code_open_paths: List[str] = []
            if role_prompt_path is not None:
                code_open_paths.append(str(role_prompt_path.resolve()))
            code_open_paths.extend(
                [
                    "docs/PROJECT_CONTEXT.md",
                    "docs/NOW.md",
                    "docs/SESSION_NOTES.md",
                    "docs/AGENT_SESSION_PROTOCOL.md",
                ]
            )
            try:
                subprocess.run(
                    [code_exe, *code_open_paths],
                    cwd=project_root,
                    check=False,
                )
            except (FileNotFoundError, OSError) as exc:
                print(f"WARNING: Failed to open docs in VS Code: {exc}")
                print("Open docs manually.")
        else:
            print("VS Code 'code' CLI not found; open docs manually.")

def print_session_end(project_root: Path, commit_enabled: bool) -> None:
    print("Local MCP – End Session")
    print("")
    branch = current_branch(project_root)
    if branch:
        print(f"Current Git branch: {branch}")
        print("")

    print("SESSION END")
    print("")
    print("1) Copy the block below into your local code agent.")
    print("2) Let it update docs (SESSION_NOTES, NOW, summaries).")
    if commit_enabled:
        print("3) Come back here and press Enter to commit & push.")
        print("   Note: --commit stages and commits all changes in the repo.")
    else:
        print("3) Come back here when the agent is done.")
    print("")
    lines = [
        "SESSION END – PROJECT CONTEXT",
        "",
        "You are a local code assistant working on this project.",
        "",
        "1. Read these again to refresh context:",
        "   - docs/PROJECT_CONTEXT.md",
        "   - docs/NOW.md",
        "   - docs/SESSION_NOTES.md",
        "",
        "2. Based on what we did this session (my notes below) and the current repo state,",
        "   UPDATE THESE FILES DIRECTLY in the workspace:",
        "",
        "   - docs/PROJECT_CONTEXT.md",
        "     *Only if any high-level design / tech decisions changed.*",
        "     *If it has a SUMMARY block between SUMMARY_START and SUMMARY_END, update that summary.*",
        "",
        "   - docs/NOW.md",
        "     Update to reflect the next immediate focus / short-term tasks.",
        "     Also refresh its SUMMARY block if present.",
        "",
        "   - docs/SESSION_NOTES.md",
        "     Append a new dated session entry (do not overwrite previous ones)",
        "     with:",
        "       - Participants",
        "       - Branch name",
        "       - Summary of work",
        "       - Files touched",
        "       - Decisions made",
        "",
        "3. When you are done updating the files, reply with:",
        "   - 3–6 bullet points summarising the session",
        "   - A list of the files you modified",
        "",
        "Here is my brief description of what we did this session:",
        "[WRITE 2–5 BULLET POINTS HERE BEFORE SENDING TO THE AGENT]",
    ]
    print("\n".join(lines))

def commit_session(project_root: Path, remote: str) -> None:
    run_git(["add", "-A"], cwd=project_root)

    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root, capture=True).strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_message = f"Session update - {timestamp}"

    changes = run_git(["status", "--porcelain"], cwd=project_root, capture=True).strip()
    if changes:
        run_git(["commit", "-m", commit_message], cwd=project_root)
    else:
        print("No changes to commit.")

    run_git(["push", remote, branch], cwd=project_root)
    print(f"Pushed branch '{branch}' to {remote}.")

def parse_args(argv: Optional[List[str]] = None):
    ap = argparse.ArgumentParser(prog="handoffkit", description="Universal (LLM-agnostic) handoff prompt builder")
    subparsers = ap.add_subparsers(dest="command")

    role_parser = subparsers.add_parser("role", help="Generate a role handoff prompt")
    role_parser.add_argument("role", choices=ROLE_CHOICES, help="Role prompt to generate")
    role_parser.add_argument("instruction", help="What you want this role to do")
    role_parser.add_argument("--root", default=".", help="Path to (or inside) your project root. Can be run from anywhere.")
    role_parser.add_argument("--config", default=None, help="Path to config JSON (optional). If omitted, auto-discovered.")
    role_parser.add_argument("--selection-file", default=None, help="Path to a file containing your selected snippet (optional)")
    role_parser.add_argument("--diff", default=None, help="Path to a diff file, or '-' to read diff from stdin (optional)")
    role_parser.add_argument("--spec", default=None, help="Path to SPEC.md (optional; overrides config)")
    role_parser.add_argument("--invariants", default=None, help="Path to invariants file (optional; overrides config)")
    role_parser.add_argument("--no-spec", action="store_true", help="Do not include SPEC.md in the handoff pack")
    role_parser.add_argument("--no-invariants", action="store_true", help="Do not include invariants in the handoff pack")

    session_parser = subparsers.add_parser("session", help="Start or end a session")
    session_subparsers = session_parser.add_subparsers(dest="session_command", required=True)

    start_parser = session_subparsers.add_parser("start", help="Print the session start prompt")
    start_parser.add_argument("--root", default=".", help="Path to (or inside) your project root. Can be run from anywhere.")
    start_parser.add_argument("--agent-role", default="Coder", choices=SESSION_ROLE_CHOICES, help="Agent role to reference")
    start_parser.add_argument("--open-docs", action="store_true", help="Open memory docs in VS Code if available")

    end_parser = session_subparsers.add_parser("end", help="Print the session end prompt")
    end_parser.add_argument("--root", default=".", help="Path to (or inside) your project root. Can be run from anywhere.")
    end_parser.add_argument("--commit", action="store_true", help="Commit and push after the agent updates docs")
    end_parser.add_argument("--remote", default="origin", help="Git remote name to push to")

    preflight_parser = subparsers.add_parser("preflight", help="Validate memory docs and required artifacts")
    preflight_parser.add_argument("--root", default=".", help="Path to (or inside) your project root. Can be run from anywhere.")
    preflight_parser.add_argument("--config", default=None, help="Path to config JSON (optional). If omitted, auto-discovered.")

    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] in ROLE_CHOICES:
        argv = ["role"] + argv
    if not argv:
        ap.print_help()
        sys.exit(2)
    return ap.parse_args(argv)

def main():
    args = parse_args()
    tool_root = Path(__file__).resolve().parent

    if args.command == "session":
        invocation_root = Path(args.root).resolve()
        project_root = find_project_root(invocation_root)
        if args.session_command == "start":
            print_session_start(project_root, tool_root, args.agent_role, args.open_docs)
            return
        if args.session_command == "end":
            print_session_end(project_root, args.commit)
            if args.commit:
                print("")
                input("After the agent has updated the docs and you're happy with the changes, press Enter here to commit & push")
                commit_session(project_root, args.remote)
            return

    if args.command == "preflight":
        invocation_root = Path(args.root).resolve()
        project_root = find_project_root(invocation_root)
        cfg = load_config(project_root, tool_root, args.config)
        sys.exit(preflight_report(project_root, cfg))

    invocation_root = Path(args.root).resolve()

    project_root = find_project_root(invocation_root)

    cfg = load_config(project_root, tool_root, args.config)

    try:
        selection = read_optional_input(args.selection_file, project_root=project_root, label="Selection")
        diff_text = read_optional_input(args.diff, project_root=project_root, label="Diff")
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        print("\nTip: generate a diff file with `git diff > patch.diff` and pass `--diff patch.diff`, or use `--diff -` to pipe stdin.", file=sys.stderr)
        sys.exit(2)

    spec_path = args.spec if args.spec is not None else cfg.get("spec_file", "SPEC.md")
    invariants_path = args.invariants if args.invariants is not None else cfg.get("invariants_file", "docs/INVARIANTS.md")

    auto_include_spec = bool(cfg.get("auto_include_spec", True))
    auto_include_invariants = bool(cfg.get("auto_include_invariants", True))
    require_spec = bool(cfg.get("require_spec", False))
    require_invariants = bool(cfg.get("require_invariants", False))

    if args.no_spec:
        if require_spec:
            print("SPEC.md is required by config; --no-spec is not allowed.", file=sys.stderr)
            sys.exit(2)
        auto_include_spec = False
    if args.no_invariants:
        if require_invariants:
            print("Invariants are required by config; --no-invariants is not allowed.", file=sys.stderr)
            sys.exit(2)
        auto_include_invariants = False

    try:
        spec_content = None
        spec_title = None
        if auto_include_spec:
            spec_content, spec_resolved = read_artifact_file(
                spec_path, project_root=project_root, label="SPEC.md", required=require_spec
            )
            if spec_content and spec_resolved:
                try:
                    spec_title = str(spec_resolved.relative_to(project_root))
                except ValueError:
                    spec_title = spec_resolved.as_posix()

        invariants_content = None
        invariants_title = None
        if auto_include_invariants:
            invariants_content, invariants_resolved = read_artifact_file(
                invariants_path, project_root=project_root, label="Invariants", required=require_invariants
            )
            if invariants_content and invariants_resolved:
                invariants_title = "Invariants"
    except (FileNotFoundError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    role_prompt, agent_path = load_role_prompt(project_root, tool_root, args.role)

    pack = build_context_pack(
        project_root,
        cfg,
        args.instruction,
        selection,
        diff_text,
        role_name=args.role,
        role_agent_path=agent_path,
        spec_content=spec_content,
        spec_title=spec_title,
        invariants_content=invariants_content,
        invariants_title=invariants_title,
    )

    print(role_prompt + "\n\n" + pack)

if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit as st
from src.config import (
    AI_PROVIDER,
    APP_DESCRIPTION,
    APP_TITLE,
    PROVIDER_SETTINGS,
    USE_MOCK_PROVIDER,
)
from src.project_manager import (
    get_file_tree,
    get_project_summary,
    is_supported_source_file,
    read_text_file,
    safe_extract_zip,
    write_text_file,
)
from src.llm_client import OpenAICompatibleLLMClient, get_llm_client
from src.repair_agent import analyze_failure

EXAMPLE_CASES = {
    "Division by zero": {
        "source": "def divide(a, b):\n    return a / b\n\nprint(divide(10, 0))\n",
        "traceback": "Traceback (most recent call last):\n  File \"script.py\", line 3, in <module>\n    print(divide(10, 0))\nZeroDivisionError: division by zero",
        "prompt": "Fix the bug and add a safe division guard.",
    },
    "Index out of range": {
        "source": "items = [10, 20, 30]\nprint(items[10])\n",
        "traceback": "Traceback (most recent call last):\n  File \"script.py\", line 2, in <module>\n    print(items[10])\nIndexError: list index out of range",
        "prompt": "Prevent invalid list access and explain the fix.",
    },
}

NAV_ITEMS = [
    ("Dashboard", "📊"),
    ("Project Explorer", "📁"),
    ("Code Repair", "🩺"),
    ("Tests", "🧪"),
    ("GitHub", "🔗"),
    ("Deploy", "🚀"),
]
MAX_UPLOAD_FILE_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_ARCHIVE_BYTES = 25 * 1024 * 1024


def inject_sidebar_css() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b1020 0%, #0f172a 100%);
            border-right: 1px solid rgba(148, 163, 184, 0.14);
        }
        [data-testid="stSidebar"] .sidebar-content {
            padding-top: 0.7rem;
            background: transparent;
        }
        .pp-brand-header {
            font-size: 1.18rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: #f8fafc;
            padding: 0.2rem 0.5rem 0.8rem 0.5rem;
            margin: 0.1rem 0 0.35rem 0;
            border-bottom: 1px solid rgba(148, 163, 184, 0.18);
        }
        .pp-nav-label {
            margin: 0.85rem 0.5rem 0.45rem 0.5rem;
            color: rgba(148, 163, 184, 0.8);
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            opacity: 0.9;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {
            gap: 0.4rem;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            box-sizing: border-box;
            min-height: 2.7rem;
            padding: 0.65rem 0.8rem;
            border: 1px solid transparent;
            border-radius: 0.8rem;
            color: #e2e8f0;
            font-size: 0.94rem;
            font-weight: 600;
            transition: background-color 0.2s ease, border-color 0.2s ease;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
            background: rgba(148, 163, 184, 0.07);
            border-color: rgba(148, 163, 184, 0.12);
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
            background: linear-gradient(90deg, rgba(59, 130, 246, 0.16), rgba(15, 118, 110, 0.08));
            border-color: rgba(96, 165, 250, 0.35);
            box-shadow: inset 3px 0 #60a5fa;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label:focus-within {
            outline: 2px solid #60a5fa;
            outline-offset: 2px;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label input[type="radio"] {
            accent-color: #60a5fa;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_nav() -> str:
    with st.sidebar:
        st.markdown('<div class="pp-brand-header">PatchPilot AI</div>', unsafe_allow_html=True)
        st.markdown('<div class="pp-nav-label">Navigation</div>', unsafe_allow_html=True)
        selected_page = st.radio(
            "Navigation",
            options=[page for page, _ in NAV_ITEMS],
            format_func=lambda page: f"{dict(NAV_ITEMS)[page]}  {page}",
            key="selected_page",
            label_visibility="collapsed",
            captions=None,
        )
    return selected_page


def init_session_state() -> None:
    st.session_state.setdefault("project_dir", None)
    st.session_state.setdefault("selected_file", None)
    st.session_state.setdefault("recent_projects", [])
    st.session_state.setdefault("repair_result", None)
    st.session_state.setdefault("last_test_result", None)
    st.session_state.setdefault("selected_page", "Dashboard")


def register_recent_project(name: str) -> None:
    projects = st.session_state.get("recent_projects", [])
    if not any(item.get("name") == name for item in projects):
        projects.append({"name": name, "status": "Ready"})
    st.session_state["recent_projects"] = projects[-5:]


def create_project_from_uploaded_files(uploaded_files) -> str | None:
    if not uploaded_files:
        return None

    project_root = Path(tempfile.mkdtemp(prefix="patchpilot-project-"))
    try:
        for uploaded in uploaded_files:
            file_name = uploaded.name
            if not file_name or "/" in file_name or "\\" in file_name or file_name in {".", ".."}:
                raise ValueError(f"Upload filename must not contain a path: {file_name!r}")

            upload_bytes = uploaded.getvalue()
            if file_name.lower().endswith(".zip"):
                if len(upload_bytes) > MAX_UPLOAD_ARCHIVE_BYTES:
                    raise ValueError("ZIP upload exceeds the 25 MB compressed-size limit.")
                zip_bytes = uploaded.getvalue()
                safe_extract_zip(zip_bytes, project_root)
            elif is_supported_source_file(file_name):
                if len(upload_bytes) > MAX_UPLOAD_FILE_BYTES:
                    raise ValueError(f"File exceeds the 2 MB limit: {file_name}")
                target_path = project_root / file_name
                if target_path.exists():
                    raise ValueError(f"Multiple uploads contain the same path: {file_name}")
                target_path.write_bytes(upload_bytes)
            else:
                st.warning(f"Skipped unsupported file: {file_name}")

        if not get_file_tree(project_root):
            raise ValueError("No supported project files were uploaded.")
    except Exception as exc:
        shutil.rmtree(project_root, ignore_errors=True)
        st.error(f"Project upload failed: {exc}")
        return None

    st.session_state["project_dir"] = str(project_root)
    st.session_state["selected_file"] = None
    register_recent_project(project_root.name)
    return str(project_root)


def build_file_tree(project_dir: str | None) -> list[str]:
    if not project_dir:
        return []
    return get_file_tree(project_dir)


def run_python_tests(project_dir: str, timeout_seconds: int = 45) -> dict[str, object]:
    if not project_dir or not Path(project_dir).is_dir():
        return {"status": "blocked", "output": "No project directory selected."}

    try:
        safe_env = {
            key: os.environ[key]
            for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
            if key in os.environ
        }
        safe_env.update(
            {
                "PYTHONNOUSERSITE": "1",
                "PYTHONPATH": str(Path(project_dir).resolve()),
            }
        )
        process = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=Path(project_dir).resolve(),
            env=safe_env,
        )
        return {
            "status": "passed" if process.returncode == 0 else "failed",
            "returncode": process.returncode,
            "output": (process.stdout or "") + (process.stderr or ""),
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "output": "Test execution timed out."}
    except FileNotFoundError:
        return {"status": "blocked", "output": "pytest is not available in the project environment."}


def run_lint_check(project_dir: str, timeout_seconds: int = 30) -> dict[str, object]:
    if not project_dir:
        return {"status": "blocked", "output": "No project directory selected."}

    try:
        process = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", "."],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=project_dir,
        )
        return {
            "status": "passed" if process.returncode == 0 else "failed",
            "returncode": process.returncode,
            "output": (process.stdout or "") + (process.stderr or ""),
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "output": "Lint/compilecheck timed out."}


def render_dashboard() -> None:
    st.subheader("Project dashboard")
    st.caption("Upload a project ZIP or individual source files to begin analysis.")

    if USE_MOCK_PROVIDER:
        st.info("AI provider: mock mode. Suggestions are local heuristics, not model inference.")
    elif AI_PROVIDER not in PROVIDER_SETTINGS:
        st.error(f"Unsupported AI_PROVIDER: {AI_PROVIDER}")
    elif not PROVIDER_SETTINGS[AI_PROVIDER]["api_key"]:
        st.warning(
            f"{PROVIDER_SETTINGS[AI_PROVIDER]['name']} is selected, but its API key is missing."
        )
    else:
        provider_settings = PROVIDER_SETTINGS[AI_PROVIDER]
        st.info(
            f"{provider_settings['name']} is configured with model "
            f"`{provider_settings['model']}`. Connectivity is not yet verified."
        )
        if st.button("Test live AI connection"):
            try:
                client = get_llm_client()
                if not isinstance(client, OpenAICompatibleLLMClient):
                    raise RuntimeError("Live provider client is unavailable.")
                client.test_connection()
                st.success(
                    f"Live inference request succeeded using {provider_settings['name']} "
                    f"and `{provider_settings['model']}`."
                )
            except Exception as exc:
                st.error(f"AI connection test failed ({type(exc).__name__}): {exc}")

    uploaded_files = st.file_uploader(
        "Upload project ZIP or source files",
        type=["zip", "py", "js", "ts", "jsx", "tsx", "java", "cpp", "c", "h", "hpp", "cs", "go", "rs", "md", "txt"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        create_project_from_uploaded_files(uploaded_files)

    if st.session_state.get("project_dir"):
        summary = get_project_summary(st.session_state["project_dir"])
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Files", summary["file_count"])
        col2.metric("Languages", len(summary["languages"]))
        col3.metric("Frameworks", len(summary["frameworks"]))
        col4.metric("Tests", "Yes" if summary["has_tests"] else "No")

        st.subheader("Recent projects")
        for item in st.session_state.get("recent_projects", []):
            st.write(f"- {item['name']} — {item['status']}")

        st.subheader("Project status")
        st.json({
            "languages": summary["languages"],
            "frameworks": summary["frameworks"],
            "has_tests": summary["has_tests"],
            "has_requirements": summary["has_requirements"],
        })
    else:
        st.info("No project loaded yet. Upload a ZIP archive or source files to begin.")


def render_explorer() -> None:
    st.subheader("Project explorer")
    project_dir = st.session_state.get("project_dir")
    if not project_dir:
        st.info("Upload a project first.")
        return

    files = build_file_tree(project_dir)
    if not files:
        st.warning("No supported project files were found.")
        return

    if st.session_state.get("selected_file") not in files:
        st.session_state["selected_file"] = files[0]
    selected_file = st.selectbox("Select file", files, key="explorer_selected_file")
    st.session_state["selected_file"] = selected_file

    file_path = Path(project_dir) / selected_file
    file_text = read_text_file(file_path)
    editor_key = f"explorer_editor:{selected_file}"
    if editor_key not in st.session_state:
        st.session_state[editor_key] = file_text
    edited_value = st.text_area("File contents", key=editor_key, height=420)
    if st.button("Save file"):
        write_text_file(file_path, edited_value)
        st.success(f"Saved {selected_file}")

    st.caption("Upload limits: maximum individual source files are kept modest to avoid large scans. Secret files, .env files, and virtualenv directories are excluded from scanning.")


def render_repair() -> None:
    st.subheader("Code repair")
    project_dir = st.session_state.get("project_dir")
    if project_dir and st.session_state.get("selected_file"):
        selected_file = st.session_state["selected_file"]
        source_to_fix = read_text_file(Path(project_dir) / selected_file)
        target_file = selected_file
        target_id = f"{project_dir}:{selected_file}"
    else:
        selected_example = st.selectbox("Example", list(EXAMPLE_CASES.keys()))
        source_to_fix = EXAMPLE_CASES[selected_example]["source"]
        target_file = None
        target_id = f"example:{selected_example}"

    if st.session_state.get("_repair_editor_target") != target_id:
        st.session_state["repair_source_editor"] = source_to_fix or ""
        st.session_state["_repair_editor_target"] = target_id
    source_code = st.text_area("Source code to analyze", height=260, key="repair_source_editor")
    default_traceback = (
        EXAMPLE_CASES[selected_example]["traceback"] if target_file is None else ""
    )
    traceback_text = st.text_area("Traceback / error output", value=default_traceback, height=140)
    user_prompt = st.text_input("Repair instructions", value="Fix the bug with minimal changes.")

    if st.button("Diagnose and repair"):
        with st.spinner("Analyzing the project and proposing a repair..."):
            try:
                repair_result = analyze_failure(source_code, traceback_text, user_prompt)
                repair_result["original_code"] = source_code
                repair_result["target_file"] = target_file
                repair_result["target_id"] = target_id
                st.session_state["repair_result"] = repair_result
            except Exception as exc:
                st.session_state["repair_result"] = None
                st.error(f"Analysis failed ({type(exc).__name__}): {exc}")

    repair_result = st.session_state.get("repair_result")
    if repair_result and repair_result.get("target_id") != target_id:
        repair_result = None
    if repair_result:
        st.info(
            f"Result source: {repair_result.get('provider')} | "
            f"status: {repair_result.get('status')}"
        )
        st.subheader("Root cause")
        st.write(repair_result.get("diagnosis", "No diagnosis available."))

        st.subheader("Repair plan")
        st.write(repair_result.get("repair_plan", "No repair plan available."))

        st.subheader("Proposed code")
        st.code(repair_result.get("fixed_code", ""), language="python")

        st.subheader("Unified diff")
        st.code(repair_result.get("diff", "") or "No patch generated.", language="diff")

        col1, col2, col3 = st.columns(3)
        can_apply = bool(
            target_file
            and repair_result.get("fixed_code") != repair_result.get("original_code")
        )
        if col1.button("Apply patch", disabled=not can_apply):
            target_path = (Path(project_dir) / target_file).resolve()
            project_root = Path(project_dir).resolve()
            if project_root not in target_path.parents:
                st.error("Patch target is outside the loaded project.")
            elif read_text_file(target_path) != repair_result["original_code"]:
                st.error("The file changed after analysis. Re-analyze before applying this patch.")
            elif target_path.suffix.lower() == ".py":
                try:
                    compile(repair_result["fixed_code"], str(target_path), "exec")
                except SyntaxError as exc:
                    st.error(f"Patch was not applied because it has a Python syntax error: {exc}")
                else:
                    st.session_state["repair_undo"] = {
                        "path": str(target_path),
                        "original_code": repair_result["original_code"],
                    }
                    write_text_file(target_path, repair_result["fixed_code"])
                    st.success("Patch applied. No tests have been run automatically.")
            else:
                st.session_state["repair_undo"] = {
                    "path": str(target_path),
                    "original_code": repair_result["original_code"],
                }
                write_text_file(target_path, repair_result["fixed_code"])
                st.success("Patch applied. No tests have been run automatically.")
        if col2.button("Reject patch"):
            st.session_state["repair_result"] = None
            st.info("Patch rejected. Original code remains in place.")
        undo = st.session_state.get("repair_undo")
        undo_enabled = bool(target_file and undo and undo.get("path") == str((Path(project_dir) / target_file).resolve()))
        if col3.button("Undo changes", disabled=not undo_enabled):
            target_path = Path(undo["path"])
            write_text_file(target_path, undo["original_code"])
            st.session_state.pop("repair_undo", None)
            st.success("Restored the original file content.")


def render_tests() -> None:
    st.subheader("Automated testing")
    project_dir = st.session_state.get("project_dir")
    if not project_dir:
        st.info("Upload a project first to run tests.")
        return

    st.warning(
        "Running tests executes project code. Only continue with source you trust; "
        "the app uses a timeout and a reduced environment, not a full security sandbox."
    )
    trusted_project = st.checkbox("I trust this project and authorize running its tests.")
    if st.button("Run tests", disabled=not trusted_project):
        st.session_state["last_test_result"] = run_python_tests(project_dir)
    if st.button("Python syntax compile check"):
        st.session_state["last_test_result"] = run_lint_check(project_dir)

    result = st.session_state.get("last_test_result")
    if result:
        st.write(f"Status: {result.get('status')}")
        st.code(result.get("output", "No output."))

    st.caption("Verified test execution is required before claiming a fix is working. If a test fails, the result is shown without guessing.")


def render_github() -> None:
    st.subheader("GitHub integration")
    repo_url = st.text_input("Repository URL", value="https://github.com/your-org/your-repo")
    branch_name = st.text_input("Branch", value="main")

    if st.button("Validate setup"):
        st.info("This UI prepares an import workflow. Actual push, PR, or token-based auth requires explicit provider authorization outside the app.")
        st.code(f"git clone {repo_url}\ngit checkout -b patchpilot-fix\n# commit and push only after user authorization")

    if st.button("Open PR preparation"):
        st.warning("Pull-request creation is blocked until the user authorizes the repository and authenticates securely. Tokens must never be pasted into ordinary text fields.")

    st.caption("Secure auth is required. Do not ask users to paste personal access tokens into the interface or expose them in logs.")


def render_deploy() -> None:
    st.subheader("Deployment center")
    provider = st.selectbox("Platform", ["Streamlit Community Cloud", "Hugging Face Spaces", "Vercel", "Manual config only"])
    if provider == "Streamlit Community Cloud":
        st.code(
            "# Streamlit deployment config\n"
            "# 1. Push repo publicly\n"
            "# 2. Connect repo in Streamlit Community Cloud\n"
            "# 3. Add NEBIUS_API_KEY from a secure environment variable\n"
            "# 4. Deploy and verify health checks\n"
        )
    elif provider == "Hugging Face Spaces":
        st.code(
            "# Hugging Face Spaces config\n"
            "# 1. Create a Space\n"
            "# 2. Configure secrets for NEBIUS_API_KEY\n"
            "# 3. Ensure the app uses a supported Python runtime\n"
        )
    elif provider == "Vercel":
        st.code(
            "# Vercel config\n"
            "# 1. Import repository\n"
            "# 2. Set environment variables securely\n"
            "# 3. Verify build logs before launch\n"
        )
    else:
        st.info("Manual deployment workflow selected. No live deployment is attempted without explicit provider authorization and successful verification.")

    st.warning("Deployment does not imply a successful public app. Health checks and environment validation are still required before claiming launch success.")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🩺")
    init_session_state()
    inject_sidebar_css()
    st.title(APP_TITLE)
    st.caption(APP_DESCRIPTION)

    if USE_MOCK_PROVIDER:
        st.warning("Mock mode is active. Results are not real model inference.")
    elif AI_PROVIDER not in PROVIDER_SETTINGS:
        st.error(f"Unsupported AI_PROVIDER: {AI_PROVIDER}")
    elif not PROVIDER_SETTINGS[AI_PROVIDER]["api_key"]:
        api_key_variable = "NVIDIA_API_KEY" if AI_PROVIDER == "nvidia_nim" else "NEBIUS_API_KEY"
        st.warning(
            f"Live mode is selected but {api_key_variable} is missing. "
            "Live inference is unavailable until it is configured."
        )
    else:
        st.info(
            f"{PROVIDER_SETTINGS[AI_PROVIDER]['name']} is configured; "
            "the model is not verified until a live request succeeds."
        )

    page = render_sidebar_nav()

    if page == "Dashboard":
        render_dashboard()
    elif page == "Project Explorer":
        render_explorer()
    elif page == "Code Repair":
        render_repair()
    elif page == "Tests":
        render_tests()
    elif page == "GitHub":
        render_github()
    else:
        render_deploy()


if __name__ == "__main__":
    main()

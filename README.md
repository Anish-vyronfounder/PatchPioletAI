# PatchPilot AI

PatchPilot AI is a beginner-friendly debugging and repair assistant for Python code. It helps developers describe a bug, inspect a traceback, and generate a minimal repair suggestion with a visible diff and testing guidance.

## Problem

Students and small-project developers often spend too much time diagnosing tracebacks, modifying code by guesswork, and rerunning tests without evidence.

## Features

- Clean Streamlit interface
- Source code and traceback input
- Example-based debugging scenarios
- Diagnosis and repair plan generation
- Unified diff display
- Safe local test execution for example scripts
- Mock model mode when no API key is configured
- Clear warnings that mock output is not a real inference result

## Architecture

```text
app.py
  └── Streamlit UI
        ├── src/config.py         # environment and settings
        ├── src/llm_client.py      # local mock or Nebius-compatible API client
        ├── src/repair_agent.py    # diagnosis and minimal repair workflow
        ├── src/patch_utils.py     # diff generation and simple patch heuristics
        └── src/test_runner.py     # subprocess-based example execution
```

## Windows installation

1. Open PowerShell in the project directory.
2. Create a venv:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Environment configuration

Create a `.env` file from `.env.example` and fill in only the values you need.

```powershell
Copy-Item .env.example .env
```

Example:

```env
NEBIUS_API_KEY=your_key_here
NEBIUS_BASE_URL=https://api.nebius.com/v1
NEBIUS_MODEL=nvidia/llama-3.1-nemotron-70b-instruct
USE_MOCK_PROVIDER=true
MAX_ATTEMPTS=2
```

Keep the `.env` file private and do not commit it.

## Run the app

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

## Offline tests

```powershell
.\.venv\Scripts\Activate.ps1
pytest -q
```

## Real inference

If you have a valid Nebius API key and a supported model endpoint, set `NEBIUS_API_KEY` and `USE_MOCK_PROVIDER=false`, then run the app. The app will attempt to make an OpenAI-compatible request to the configured Nebius base URL.

This project does not claim to be a live Nebius integration until a real request is actually checked.

## Security and limitations

- User code is never executed inside the main Streamlit process.
- Example execution is done in a subprocess with a temporary working directory.
- This is not a full security sandbox and should not be treated as a guaranteed isolation boundary for arbitrary untrusted code.
- Mock mode is clearly labeled and must not be represented as real model output.

## Licenses and acknowledgements

- This project uses the MIT license.
- Streamlit, OpenAI, python-dotenv, and pytest are third-party dependencies listed in `requirements.txt`.
- Nebius and NVIDIA model access must be verified by the user before claiming real runtime integration.

## Compliance status

This project currently satisfies the local MVP requirements for a Python debugging assistant: a working Streamlit UI, safe local execution, diff display, and regression tests. However, the live Nebius + NVIDIA model requirement is not yet verified because no real API key is present in this environment. The app therefore runs in explicit mock mode by default and clearly labels that status.

### Verified items

- Python project scaffold and working dependency install
- Streamlit frontend boots successfully
- Local regression tests run successfully
- Model client abstraction exists
- `.env` values are separated from source control
- `.gitignore` excludes `.env`

### Unverified or blocked items

- Real Nebius Token Factory request
- Valid NVIDIA open-source model ID on this account
- Public repository publication
- Deployment to a public URL
- Demo video under three minutes
- Final Devpost submission and proof of eligibility

## Publishing and submission checklist

1. Create a public GitHub repository.
2. Push the contents of this project without committing `.env` or real credentials.
3. Add a license and documentation to the public repo.
4. Configure the host or environment with a real Nebius API key.
5. Set `USE_MOCK_PROVIDER=false` and validate a real chat/completions request.
6. Confirm the selected model is a qualifying NVIDIA open-source model allowed by the official rules.
7. Run the app locally and record a short demo video.
8. Publish the demo URL and README.
9. Complete the Devpost fields and submit before the deadline.

## Known limitations

- This project is intentionally simple and beginner-friendly.
- Live inference is blocked until a working Nebius credential and valid model access are available.
- The required hackathon compliance claim cannot be made until the runtime integration is validated.

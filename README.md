# Lab 4B: Ask the Panel

DAMG 7245 Big Data and Intelligent Analytics, Fall 2026: Project LANTERN, Tool Tutorial Part 4B.

**Due Friday 20 November 2026, 3:59 p.m. ET.** 100 points, plus up to 5 bonus points.

Build a natural-language query interface over your Lab 3B BDC panel. An analyst types a question; a LangGraph
agent writes one SQL query as a Pydantic object, runs it through your MCP query server, and answers with the
rows and the SQL behind them.

## What's here

| File | What it is |
|---|---|
| [`LANTERN_Lab4B_Brief.pdf`](LANTERN_Lab4B_Brief.pdf) | The assignment: the seven parts, grading, and how to submit. **Start here.** |
| [`LANTERN_Tool_Tutorial_Part4B.pdf`](LANTERN_Tool_Tutorial_Part4B.pdf) | The tutorial deck for Labs 32B–36B. Each lab ends with a "Your turn" slide. |
| [`cs4b/`](cs4b) | The starter kit: notebooks, the `askpanel` building blocks, the fixture panel, tests and a self-check |

You can also download the starter kit as one zip from this repository's **Releases**.

## Get started

1. Copy the `cs4b/` folder into your **Lab 3B team repository**, next to `cs3b/`. Run every command from
   inside `cs4b/`.
2. Use **Python 3.11 or later**, and install:

   macOS / Linux:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
   Windows (PowerShell):
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Check the kit, then open the notebooks:
   ```bash
   python tests/run_tests.py        # 26/26 tests pass
   python tools/run_notebooks.py    # 6/6 notebooks run end to end
   jupyter lab                      # start with notebooks/00_setup.ipynb
   ```
4. Read the brief, then work through the deck lab by lab. `cs4b/README.md` lists what you build, file by file.

## Good to know

- `requirements.txt` installs the exact versions the kit was tested with, using `constraints.txt`. Keep both files.
- **Record mode** needs a free Gemini API key from Google AI Studio. Set it in your terminal only
  (`export GEMINI_API_KEY=...`, or `$env:GEMINI_API_KEY="..."` in PowerShell). **Never commit it.**
  Replay, the tests and grading need no key.
- **Windows:**
  - If `streamlit` is blocked, run `python -m streamlit run app/streamlit_app.py`.
  - Keep your repository in a short path such as `C:\dev\team-repo`; very long paths can make `pip install` fail.
- Your team repository stays **private** until grades are returned. Submit as the brief describes: a tagged
  commit `cs4b-submission`, and a demo video of at most 10 minutes linked from `cs4b/README.md`.

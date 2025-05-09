# gemini-pr-reviewer

A lightweight CLI for automating PR reviews with Google’s Gemini AI. You feed it:

- a ZIP of your source
- a user-story file (and optional acceptance-criteria file)
- it uploads, processes, and prompts Gemini to verify that your code meets your requirements.

After each run it cleans up your uploads (unless you override), and always shows you what’s left in Vertex AI storage—so you never lose track of stray files.

## Features

- **Automated upload & cleanup**
  Uploads your ZIP, polls until it’s ACTIVE, then deletes it on exit.

- **Customizable prompts**
  Builds system-level and user-level instructions from your story + criteria.

- **Configurable output**
  Writes feedback to a file by default; `--show-feedback` echoes it in your console.

- **Storage visibility**
  Always lists remaining files in Vertex AI so you can spot leftovers.

- **One-off or bulk cleanup**
  `--cleanup-files` deletes every upload you’ve ever made, then lists what remains.

- **List only**
  `--list-files` shows all stored files without doing a review or cleanup.

## Installation

1. Clone or download this repo
2. `pip install -r requirements.txt`
3. Create a `.env` file with:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

## Usage

### Review a PR (default)

```bash
python pr_review.py \
  -z path/to/project.zip \
  -s path/to/user_story.txt \
  -c path/to/criteria.txt \
  -o feedback.md
```

By default this writes to `feedback.md` and, after cleanup, lists any remaining files.
Add `--show-feedback` to also print the feedback in your terminal.

### List stored files

```bash
python pr_review.py --list-files
```

Prints every file currently stored in Vertex AI, then exits.

### Cleanup all uploads

```bash
python pr_review.py --cleanup-files
```

Deletes every file you’ve ever uploaded via this tool, then lists what remains (ideally “none”).

## CLI Options

- `-z, --zip`           Path to project ZIP file (required for review)
- `-s, --story`         Path to user-story text file (required for review)
- `-c, --criteria`      Path to acceptance-criteria text file
- `-o, --output`        Path to save feedback markdown (required for review)
- `--show-feedback`     Also print Gemini feedback to the console
- `--list-files`        List all files currently stored in Vertex AI and exit
- `--cleanup-files`     Delete all uploaded files from Vertex AI, then list what’s left
- `--version`           Print tool version and exit

## MIT License

# gemini-pr-reviewer

A powerful CLI tool that leverages Google's Gemini AI to automate pull request reviews. This tool analyzes your source code against user stories and acceptance criteria, providing detailed feedback on implementation quality and requirements coverage.

## Features

- **AI-Powered Code Review**
  - Analyzes source code against user stories and acceptance criteria
  - Provides detailed feedback on implementation quality
  - Identifies potential issues and improvement areas

- **Flexible Input Options**
  - Support for single or multiple ZIP files
  - Customizable prompts for specific review requirements
  - Optional acceptance criteria file

- **Smart File Management**
  - Automatic upload and processing of source code
  - Configurable file retention policies
  - Built-in cleanup utilities

- **Customizable Output**
  - Markdown-formatted feedback
  - Console output options
  - Debug mode for prompt inspection

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/gemini-pr-reviewer.git
   cd gemini-pr-reviewer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

## Usage

### Basic Review

```bash
python pr_review.py \
  -z path/to/project.zip \
  -s path/to/user_story.txt \
  -p path/to/prompt.txt \
  -o feedback.md
```

### Multiple ZIP Files

```bash
python pr_review.py \
  -z before.zip after.zip \
  -s user_story.txt \
  -p prompt.txt \
  -o feedback.md
```

### With Acceptance Criteria

```bash
python pr_review.py \
  -z project.zip \
  -s user_story.txt \
  -c acceptance_criteria.txt \
  -p prompt.txt \
  -o feedback.md
```

### Custom Prompt Templates

The tool supports several placeholders in your custom prompt:

- `{ZIP_FILES_LIST}` - Lists all uploaded files with details
- `{FILE_NAME_1}`, `{DISPLAY_NAME_1}`, `{FILE_URI_1}` - First file details
- `{FILE_NAME_2}`, `{DISPLAY_NAME_2}`, `{FILE_URI_2}` - Second file details
- `{USER_STORY}` - Content of the user story file
- `{ACCEPTANCE_CRITERIA}` - Content of the acceptance criteria file

Example prompt template:
```
**Source Code:**
The complete source code for the project/feature is provided in the uploaded ZIP file(s).
{ZIP_FILES_LIST}

**User Story:**
{USER_STORY}

**Acceptance Criteria:**
{ACCEPTANCE_CRITERIA}

**Your Task:**
1. Analyze the source code against the user story and acceptance criteria
2. Verify implementation completeness
3. Identify potential issues or improvements
4. Provide detailed feedback
```

## Command Line Options

### Required Arguments
- `-z, --zip`           Path to project ZIP file(s) (one or more)
- `-s, --story`         Path to user story text file
- `-p, --prompt`        Path to custom prompt text file
- `-o, --output`        Path to save feedback markdown

### Optional Arguments
- `-c, --criteria`      Path to acceptance criteria text file
- `--show-feedback`     Print feedback to console in addition to file
- `--show-prompt`       Print the full prompt sent to Gemini (debug mode)
- `--save-prompt`       Save the full prompt to a file (debug mode)
- `--keep-files`        Retain uploaded files in Vertex AI
- `--list-files`        List all files in Vertex AI and exit
- `--cleanup-files`     Delete all files from Vertex AI and list remaining
- `--version`           Display version information

## File Management

### List Stored Files
```bash
python pr_review.py --list-files
```

### Cleanup All Files
```bash
python pr_review.py --cleanup-files
```

### Keep Files After Review
```bash
python pr_review.py -z project.zip -s story.txt -p prompt.txt -o feedback.md --keep-files
```

## Debug Options

### View Full Prompt
```bash
python pr_review.py -z project.zip -s story.txt -p prompt.txt -o feedback.md --show-prompt
```

### Save Prompt to File
```bash
python pr_review.py -z project.zip -s story.txt -p prompt.txt -o feedback.md --save-prompt=debug_prompt.txt
```

## Limitations

- Maximum file size: 10MB per text file, 50MB per ZIP file
- Files are automatically cleaned up unless `--keep-files` is specified
- Requires valid Gemini API key in `.env` file

## License

MIT License

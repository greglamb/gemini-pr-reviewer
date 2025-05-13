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

### Primary Use Case: Before/After Comparison

The most common use case is comparing code before and after changes to verify pull request completeness:

```bash
python pr_review.py \
  -z before.zip after.zip \
  -s story.txt \
  -p prompt.md \
  -o feedback.md
```

This use case is ideal for:
- Verifying pull request completeness
- Comparing code changes against user stories
- Ensuring all acceptance criteria are met
- Identifying potential issues or improvements

### Sample Prompt Template

The tool comes with a sample prompt template (`prompt.md`) that provides a structured format for code reviews:

```
**Source Code:**
The complete source code for the project/feature is provided in the uploaded ZIP files:

{ZIP_FILES_LIST}

**Before and After**
- before.zip contains the complete source code before work began on this user story.
- after.zip contains the complete source code after work was allegedly completed on this user story.
- Please help me determine if this pull request is ready to be merged, and this user story is ready to be closed.

**Your Task:**
1. Thoroughly analyze the source code accessible via the provided file URI(s).
2. Verify if all stated acceptance criteria have been met.
3. Verify if all changes requested in the user story have been successfully implemented.
4. Identify any deviations, bugs, or areas where the implementation does not align.
5. Comment on code quality and potential improvements, prioritizing verification of completion.

**Output Format:**
Provide a structured feedback report:

1. **Overall Assessment:**
   * **Status:** [e.g., "Ticket Goals Met", "Ticket Partially Met", "Significant Issues Found - Not Met"]
   * **Summary:** [Provide a 1-2 sentence high-level summary of the review findings.]

2. **Detailed Findings (if any discrepancies):**
   * [For each issue/discrepancy found]
   * **Issue:** [Brief description of the problem or deviation]
   * **Reference:** [Link to relevant User Story/Ticket ID or Acceptance Criterion]
   * **Code Evidence:** [Cite specific file(s) and line number(s)]
   * **Impact:** [Briefly explain the consequence of this issue]

3. **Positive Confirmations:**
   * [List any key criteria or goals that were successfully met]

4. **Conclusion & Readiness:**
   * **Is the ticket complete as per its definition?** [Yes/No/Partially]
   * **Are we ready to proceed to next steps?** [Yes/No/No, requires addressing...]

5. **Actionable Next Steps:**
   * [Provide a clear, ordered list of specific actions needed]
```

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

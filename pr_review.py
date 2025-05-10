#!/usr/bin/env python3
"""
Gemini PR Reviewer

This script analyzes source code against user stories using Google's Gemini AI,
always lists what files remain stored in Vertex AI after it runs, and by default
writes feedback only to the file. Use --show-feedback to also print it.
Use --list-files to see stored files without doing anything else.
Use --cleanup-files to delete all stored files and then list what's left.

Example usage:
    # Normal review run, write to feedback.md only:
    python pr_review.py -z project.zip -s user_story.txt -c acceptance_criteria.txt -o feedback.md

    # Same, but also show feedback in console:
    python pr_review.py -z project.zip -s user_story.txt -c acceptance_criteria.txt \
        -o feedback.md --show-feedback

    # Just list files without deleting or reviewing:
    python pr_review.py --list-files

    # Delete all stored files, then list what's left:
    python pr_review.py --cleanup-files
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import time
import argparse
from pathlib import Path

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
import pkg_resources

print(f"Using google-generativeai version: {pkg_resources.get_distribution('google-generativeai').version}")

MODEL_NAME = "gemini-2.5-pro-preview-05-06"
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error: GEMINI_API_KEY not found in environment variables.")
    sys.exit(1)
genai.configure(api_key=API_KEY)


def list_stored_files():
    print("\nCurrently stored files in Vertex AI:")
    try:
        files = list(genai.list_files())
        if not files:
            print("  (none)")
            return
        for f in files:
            print(f"  • {f.name} (state={f.state.name})")
    except Exception as e:
        print(f"Error listing files: {e}")


def cleanup_stored_files():
    print("Cleaning up all stored files …")
    try:
        files = list(genai.list_files())
        for f in files:
            genai.delete_file(name=f.name)
        print(f"  Deleted {len(files)} file{'s' if len(files)!=1 else ''}.")
    except Exception as e:
        print(f"Error during cleanup: {e}")
        sys.exit(1)


def upload_and_process_file(file_path):
    name = Path(file_path).name
    print(f"Uploading {name} …")
    uploaded = genai.upload_file(file_path)
    while uploaded.state.name == "PROCESSING":
        print(f"  {name} state={uploaded.state.name}; retrying in 5s …")
        time.sleep(5)
        uploaded = genai.get_file(name=uploaded.name)
    if uploaded.state.name == "FAILED":
        raise Exception("Upload failed (state=FAILED)")
    print(f"  {name} is ACTIVE (URI: {uploaded.uri})")
    return uploaded


def read_text_file_content(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def run_review(args):
    uploaded = None
    try:
        if not Path(args.zip).exists():
            raise FileNotFoundError(f"ZIP not found: {args.zip}")
        if not Path(args.story).exists():
            raise FileNotFoundError(f"Story not found: {args.story}")
        if args.criteria and not Path(args.criteria).exists():
            raise FileNotFoundError(f"Criteria not found: {args.criteria}")

        uploaded = upload_and_process_file(args.zip)

        story = read_text_file_content(args.story)
        criteria = read_text_file_content(args.criteria) if args.criteria else ""
        system_inst = (
            "You are an expert QA engineer and senior software developer."
            "Your task is to meticulously review the provided source code (in the uploaded ZIP file) against the given user story and its acceptance criteria."
        )
        user_prompt = f"**User Story:**\n{story}\n"
        if criteria:
            user_prompt += f"\n**Acceptance Criteria:**\n{criteria}\n"
        else:
            user_prompt += "\n(The acceptance criteria are likely embedded within or implied by the user story. Please infer them as best as possible.)\n"

        # choose which review prompt block to append
        if args.known_incomplete:
            # In-progress review prompt
            user_prompt += f"""
**Source Code (In-Progress):**
The current in-progress source code for the project/feature is provided in the uploaded ZIP file.
File Name on Server (Resource Name): {uploaded.name}
Display Name: {Path(args.zip).name}
URI for Model Access: {uploaded.uri}

**Review Focus (In-Progress Work):**
This review is for work that is **not yet complete**. The primary goals are:
1. To assess if the current direction aligns with the ticket's objectives and architectural goals.
2. To identify any potential deviations or roadblocks early.
3. To provide constructive feedback to keep the development on track.

**Your Task:**
1. Analyze the current state of the source code accessible via the provided file URI.
2. Evaluate the implemented portions against the relevant acceptance criteria and user story goals (understanding they may not all be met yet).
3. Identify areas where the current implementation is **well-aligned** with the intended architecture and goals.
4. Identify any **potential deviations, risks, or areas needing course correction** to meet the final goals.
5. Offer feedback on code quality and potential improvements, focusing on guiding the ongoing work.

**Output Format (In-Progress Review):**
Provide a structured feedback report:

1.  **Overall Progress Assessment:**
    *   **Current Direction:** `[e.g., "On Track with Ticket Goals", "Generally Aligned, Minor Adjustments Suggested", "Potential Misalignment, Course Correction Recommended"]`
    *   **Summary:** `[Provide a 1-2 sentence high-level summary of the current progress and alignment.]`

2.  **Areas of Strong Alignment / Positive Progress:**
    *   `[List specific aspects of the current implementation that are progressing well and align with the ticket's goals or architectural principles. e.g., "The new Bar interface in @foo/something is well-structured and generic as intended."]`

3.  **Areas for Attention / Potential Course Correction (Constructive Feedback):**
    *   *(For each area needing attention):*
        *   **Observation/Concern:** `[Brief description of the observation or potential issue.]`
        *   **Reference (Intended Goal):** `[Link to relevant User Story/Ticket ID, Acceptance Criterion #, or architectural goal this observation relates to.]`
        *   **Code Evidence (Current State):** `[Cite specific file(s) and line number(s) if applicable.]`
        *   **Suggestion/Guidance:** `[Provide constructive advice or questions to guide the developer. Focus on keeping them on track rather than just pointing out incompleteness. e.g., "Consider moving the FooModel to the @bar/models directory to maintain package cohesion as per Ticket C*.", "Ensure that the circular dependency between X and Y is addressed before this component is finalized by removing import Z."]`

4.  **Key Considerations for Next Steps (Guidance, not Demands for Completion):**
    *   `[Highlight 1-3 critical aspects the developer should focus on next to ensure the work stays aligned with the ticket's ultimate goals. e.g., "Prioritize removing all text-specific exports from @foo/something.", "Focus on ensuring the \`move\` operation for model files is atomic in the next iteration."]`

5.  **General Code Quality Feedback (Optional, if noteworthy at this stage):**
    *   `[Brief comments on code style, clarity, or potential refactoring opportunities that can be incorporated as development continues.]`

**Concluding Remark:**
*   `[A brief, encouraging closing statement, reiterating the focus on guidance for ongoing work.]`
"""
        else:
            # Default (known-incomplete not set) – standard review prompt
            user_prompt += f"""
**Source Code:**
The complete source code for the project/feature is provided in the uploaded ZIP file.
File Name on Server (Resource Name): {uploaded.name}
Display Name: {Path(args.zip).name}
URI for Model Access: {uploaded.uri}

        **Your Task:**
        1. Thoroughly analyze the source code accessible via the provided file URI.
        2. Verify if all stated acceptance criteria have been met.
        3. Verify if all changes requested in the user story have been successfully implemented.
        4. Identify any deviations, bugs, or areas where the implementation does not align.
        5. Comment on code quality and potential improvements, prioritizing verification of completion.

        **Output Format:**
        Provide a structured feedback report:

        1.  **Overall Assessment:**
            *   **Status:** `[e.g., "Ticket Goals Met", "Ticket Partially Met", "Significant Issues Found - Not Met"]`
            *   **Summary:** `[Provide a 1-2 sentence high-level summary of the review findings.]`

        2.  **Detailed Findings (if any discrepancies):**
            *   *(For each issue/discrepancy found):*
                *   **Issue:** `[Brief description of the problem or deviation.]`
                *   **Reference:** `[Link to relevant User Story/Ticket ID, Acceptance Criterion #, or specific architectural goal discussed previously.]`
                *   **Code Evidence:** `[Cite specific file(s) and line number(s) where the issue is observed, if applicable. e.g., "In packages/foo/src/models/index.ts, Line X..."]`
                *   **Impact:** `[Briefly explain the consequence of this issue, e.g., "This maintains the circular dependency," "This will cause build failures in downstream packages."] `

        3.  **Positive Confirmations (if applicable):**
            *   `[List any key criteria or goals that *were* successfully met, especially if the overall status isn't fully "Met". e.g., "The new Bar interface in @something/foo is correctly implemented."]`

        4.  **Conclusion & Readiness for Next Steps:**
            *   **Is the ticket complete as per its definition?** `[Yes/No/Partially]`
            *   **Are we ready to proceed to Ticket(s) `[Next Ticket ID(s)]`?** `[Yes/No/No, requires addressing the following... ]`

        5.  **Actionable Next Steps for Developer:**
            *   `[Provide a clear, ordered list of specific actions the developer needs to take to resolve the identified issues and meet the ticket's goals. Be precise.]`
                *   *Example 1:* "1. Remove the text-specific model files (`Foo.ts`, `Bar.ts`) from `packages/example/src/models/`."
                *   *Example 2:* "2. Delete the import of `Bar` from `@foo/something` within `packages/example/src/models/index.ts`."
                *   *Example 3:* "3. Ensure all unit tests in `@foo/something` pass after these changes."
            *   *(If all criteria are met and no issues):* "No further action required for this ticket. Ready to proceed to Ticket `[Next Ticket ID]`."

        """

        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            generation_config=genai.GenerationConfig(temperature=0.3),
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT",      "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH",      "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT","threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        )

        print(f"\nSending request to {MODEL_NAME} …")
        response = model.generate_content(f"{system_inst}\n\n{user_prompt}")
        feedback = response.text

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as out:
                out.write(feedback)
            print(f"\nFeedback saved to: {args.output}")

        if args.show_feedback:
            print("\n--- Feedback ---\n")
            print(feedback)
            print("\n--- End Feedback ---")

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
    finally:
        if uploaded:
            try:
                genai.delete_file(name=uploaded.name)
            except Exception:
                pass
        list_stored_files()


def main():
    parser = argparse.ArgumentParser(
        description="Gemini PR Reviewer: analyze code or manage stored files, always list remaining."
    )
    parser.add_argument("-z", "--zip",      help="Path to project ZIP file")
    parser.add_argument("-s", "--story",    help="Path to user story text file")
    parser.add_argument("-c", "--criteria", help="Path to acceptance criteria text file")
    parser.add_argument("-o", "--output",   help="Path to save feedback markdown")
    parser.add_argument(
        "--show-feedback",
        action="store_true",
        help="Also print Gemini feedback to the console (default: write only to file)"
    )
    parser.add_argument(
        "--list-files",
        action="store_true",
        help="List all files currently stored in Vertex AI and exit"
    )
    parser.add_argument(
        "--cleanup-files",
        action="store_true",
        help="Delete all uploaded files from Vertex AI, then list what's left"
    )
    parser.add_argument(
        "--known-incomplete",
        action="store_true",
        help="Use the in-progress review prompt instead of the default full-review prompt"
    )
    parser.add_argument("--version", action="version", version="1.0.0")

    args = parser.parse_args()

    if args.list_files:
        list_stored_files()
        sys.exit(0)

    if args.cleanup_files:
        cleanup_stored_files()
        list_stored_files()
        sys.exit(0)

    if not (args.zip and args.story):
        parser.error("for review you must provide -z/--zip and -s/--story")

    args.zip     = str(Path(args.zip).resolve())
    args.story   = str(Path(args.story).resolve())
    if args.criteria:
        args.criteria = str(Path(args.criteria).resolve())
    if args.output:
        args.output   = str(Path(args.output).resolve())

    run_review(args)


if __name__ == "__main__":
    main()
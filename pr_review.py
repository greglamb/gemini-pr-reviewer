#!/usr/bin/env python3
"""
Gemini PR Reviewer

This script analyzes source code against user stories using Google's Gemini AI,
always lists what files remain stored in Vertex AI after it runs, and by default
writes feedback only to the file. Use --show-feedback to also print it.
Use --list-files to see stored files without doing anything else.
Use --cleanup-files to delete all stored files and then list what's left.

Example usage:
    # Review run with a custom prompt, write to feedback.md:
    python pr_review.py -z project.zip -s user_story.txt -c acceptance_criteria.txt -p prompt.txt -o feedback.md

    # Multiple zip files:
    python pr_review.py -z project1.zip project2.zip -s user_story.txt -c acceptance_criteria.txt -p prompt.txt -o feedback.md

    # For multiple zip files in a custom prompt, you can use these placeholder formats:
    # - {ZIP_FILES_LIST} - Lists all files with their details in a formatted block
    # - {FILE_NAME_1}, {DISPLAY_NAME_1}, {FILE_URI_1} - For the first zip file
    # - {FILE_NAME_2}, {DISPLAY_NAME_2}, {FILE_URI_2} - For the second zip file, etc.
    # - {FILE_NAME}, {DISPLAY_NAME}, {FILE_URI} - For backward compatibility (uses first file)
    # 
    # The user story and acceptance criteria will be automatically appended after your prompt.
    # If you want to include them in a specific location, you can use these placeholders:
    # - {USER_STORY} - The content of the user story file
    # - {ACCEPTANCE_CRITERIA} - The content of the acceptance criteria file (if provided)

    # Same, but also show feedback in console:
    python pr_review.py -z project.zip -s user_story.txt -c acceptance_criteria.txt -p prompt.txt \
        -o feedback.md --show-feedback

    # Show the full prompt sent to the AI (for debugging):
    python pr_review.py -z project.zip -s user_story.txt -c acceptance_criteria.txt -p prompt.txt \
        -o feedback.md --show-prompt

    # Save the full prompt to a file (for debugging):
    python pr_review.py -z project.zip -s user_story.txt -c acceptance_criteria.txt -p prompt.txt \
        -o feedback.md --save-prompt=prompt_debug.txt
        
    # Keep the uploaded files in Vertex AI (don't automatically clean up):
    python pr_review.py -z project.zip -s user_story.txt -c acceptance_criteria.txt -p prompt.txt \
        -o feedback.md --keep-files

    # Just list files without deleting or reviewing:
    python pr_review.py --list-files

    # Delete all stored files, then list what's left:
    python pr_review.py --cleanup-files
    
    # Example prompt file content:
    # ------------------------------
    # **Source Code:**
    # The complete source code for the project/feature is provided in the uploaded ZIP file(s).
    # {ZIP_FILES_LIST}
    # 
    # **Before and After**
    # - before.zip contains the complete source code before work began on this user story.
    # - after.zip contains the complete source code after work was allegedly completed on this user story.
    # - Please help me determine if this pull request is ready to be merged, and this user story is ready to be closed.
    # 
    # **Your Task:**
    # 1. Thoroughly analyze the source code accessible via the provided file URI(s).
    # 2. Verify if all stated acceptance criteria have been met.
    # 3. Verify if all changes requested in the user story have been successfully implemented.
    # 4. Identify any deviations, bugs, or areas where the implementation does not align.
    # 5. Comment on code quality and potential improvements, prioritizing verification of completion.
    # ------------------------------
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
    uploaded_files = []
    file_display_names = {}  # Dictionary to track display names
    try:
        # Validate input files
        for zip_path in args.zip:
            if not Path(zip_path).exists():
                raise FileNotFoundError(f"ZIP not found: {zip_path}")

        if not Path(args.story).exists():
            raise FileNotFoundError(f"Story not found: {args.story}")

        if args.criteria and not Path(args.criteria).exists():
            raise FileNotFoundError(f"Criteria not found: {args.criteria}")

        if args.prompt and not Path(args.prompt).exists():
            raise FileNotFoundError(f"Prompt not found: {args.prompt}")

        # Upload all zip files
        for zip_path in args.zip:
            uploaded = upload_and_process_file(zip_path)
            uploaded_files.append(uploaded)
            # Store the original filename keyed by the file's name
            file_display_names[uploaded.name] = Path(zip_path).name

        # Read the story and criteria
        story = read_text_file_content(args.story)
        criteria = read_text_file_content(args.criteria) if args.criteria else ""

        system_inst = (
            "You are an expert QA engineer and senior software developer."
            "Your task is to meticulously review the provided source code (in the uploaded ZIP file(s)) against the given user story and its acceptance criteria."
        )

        # Start with an empty prompt
        user_prompt = ""

        # Load custom prompt from file
        custom_prompt = read_text_file_content(args.prompt)

        # Check if we need to handle special placeholders for multiple files
        if "{ZIP_FILES_LIST}" in custom_prompt:
            # Create a formatted list of all zip files
            zip_files_info = ""
            for i, uploaded in enumerate(uploaded_files, 1):
                display_name = file_display_names.get(uploaded.name, "Unknown")
                zip_files_info += f"""
ZIP File #{i}:
  File Name on Server: {uploaded.name}
  Display Name: {display_name}
  URI for Model Access: {uploaded.uri}
"""
            custom_prompt = custom_prompt.replace("{ZIP_FILES_LIST}", zip_files_info)
            
        # Handle user story and acceptance criteria placeholders
        custom_prompt = custom_prompt.replace("{USER_STORY}", story)
        if criteria:
            custom_prompt = custom_prompt.replace("{ACCEPTANCE_CRITERIA}", criteria)
        else:
            custom_prompt = custom_prompt.replace("{ACCEPTANCE_CRITERIA}", 
                "(The acceptance criteria are likely embedded within or implied by the user story. Please infer them as best as possible.)")
            
        # Handle file-specific placeholders
        for i, uploaded in enumerate(uploaded_files, 1):
            display_name = file_display_names.get(uploaded.name, "Unknown")

            # Use indexed placeholders for multiple files
            custom_prompt = custom_prompt.replace(f"{{FILE_NAME_{i}}}", uploaded.name)
            custom_prompt = custom_prompt.replace(f"{{DISPLAY_NAME_{i}}}", display_name)
            custom_prompt = custom_prompt.replace(f"{{FILE_URI_{i}}}", uploaded.uri)

            # Also replace non-indexed placeholders with the first file (for backward compatibility)
            if i == 1:
                custom_prompt = custom_prompt.replace("{FILE_NAME}", uploaded.name)
                custom_prompt = custom_prompt.replace("{DISPLAY_NAME}", display_name)
                custom_prompt = custom_prompt.replace("{FILE_URI}", uploaded.uri)

        # Add custom prompt first
        user_prompt += custom_prompt
        
        # Only append the user story if it's not already included through placeholders
        if "{USER_STORY}" not in custom_prompt:
            # Add a separator
            user_prompt += "\n\n---\n\n"
            
            # Add user story after the custom prompt
            user_prompt += f"**User Story Details:**\n{story}\n"
            if criteria and "{ACCEPTANCE_CRITERIA}" not in custom_prompt:
                user_prompt += f"\n**Acceptance Criteria:**\n{criteria}\n"
            elif not criteria and "{ACCEPTANCE_CRITERIA}" not in custom_prompt:
                user_prompt += "\n(The acceptance criteria are likely embedded within or implied by the user story. Please infer them as best as possible.)\n"

        # The user story was already added at the beginning of the prompt
        # No need to add it again

        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            generation_config=genai.GenerationConfig(temperature=0.2),  # Lower temperature for more focused code reviews
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT",      "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH",      "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT","threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ],
            tools=[{
                "function_declarations": [{"name": "execute_code", "description": "Execute code in a sandbox environment"}]
            }],
        )

        print(f"\nSending request to {MODEL_NAME} …")

        full_prompt = f"{system_inst}\n\n{user_prompt}"

        # Show full prompt if requested
        if args.show_prompt:
            print("\n--- Full Prompt ---\n")
            print(full_prompt)
            print("\n--- End Full Prompt ---\n")

        # Save prompt to file if requested
        if args.save_prompt:
            with open(args.save_prompt, 'w', encoding='utf-8') as prompt_file:
                prompt_file.write(full_prompt)
            print(f"Full prompt saved to: {args.save_prompt}")

        response = model.generate_content(full_prompt)
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
        # Clean up all uploaded files unless --keep-files is specified
        if not args.keep_files:
            for uploaded in uploaded_files:
                try:
                    display_name = file_display_names.get(uploaded.name, "Unknown")
                    genai.delete_file(name=uploaded.name)
                    print(f"Deleted {display_name}")
                except Exception as e:
                    print(f"Error deleting {display_name}: {e}")
        else:
            print("Keeping uploaded files (--keep-files specified)")
        
        list_stored_files()


def main():
    parser = argparse.ArgumentParser(
        description="Gemini PR Reviewer: analyze code or manage stored files, always list remaining."
    )
    parser.add_argument("-z", "--zip",      help="Path to project ZIP file(s)", nargs='+', required=True)
    parser.add_argument("-s", "--story",    help="Path to user story text file", required=True)
    parser.add_argument("-c", "--criteria", help="Path to acceptance criteria text file")
    parser.add_argument("-p", "--prompt",   help="Path to custom user prompt text file", required=True)
    parser.add_argument("-o", "--output",   help="Path to save feedback markdown")
    parser.add_argument(
        "--show-feedback",
        action="store_true",
        help="Also print Gemini feedback to the console (default: write only to file)"
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Print the full prompt sent to the AI endpoint (for debugging)"
    )
    parser.add_argument(
        "--save-prompt",
        metavar="FILE",
        help="Save the full prompt to a file (for debugging)"
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
        "--keep-files",
        action="store_true",
        help="Keep the uploaded files in Vertex AI (don't automatically clean up)"
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

    # Resolve paths to absolute paths
    args.zip = [str(Path(z).resolve()) for z in args.zip]
    args.story = str(Path(args.story).resolve())

    if args.criteria:
        args.criteria = str(Path(args.criteria).resolve())
    if args.prompt:
        args.prompt = str(Path(args.prompt).resolve())
    if args.output:
        args.output = str(Path(args.output).resolve())
    if args.save_prompt:
        args.save_prompt = str(Path(args.save_prompt).resolve())

    run_review(args)


if __name__ == "__main__":
    main()
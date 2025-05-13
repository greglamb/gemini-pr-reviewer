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

import os
import sys
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Any

import pkg_resources
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Gemini API
try:
    import google.generativeai as genai
    from google.api_core.exceptions import GoogleAPIError
    print(f"Using google-generativeai version: {pkg_resources.get_distribution('google-generativeai').version}")
except ImportError as e:
    print(f"Error: Required package not found: {e}")
    print("Please install required packages with: pip install google-generativeai python-dotenv")
    sys.exit(1)

# Constants
MODEL_NAME = "gemini-2.5-pro-preview-05-06"
MAX_FILE_SIZE_MB = 10
MAX_ZIP_SIZE_MB = 50
MAX_UPLOAD_RETRIES = 12
UPLOAD_RETRY_DELAY_SEC = 5


class GeminiReviewer:
    """Main class for handling PR reviews with Gemini AI"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("Error: GEMINI_API_KEY not found in environment variables.")
            sys.exit(1)
        genai.configure(api_key=self.api_key)
        self.uploaded_files = []
        self.file_display_names = {}
    
    def validate_api_key(self) -> bool:
        """Validate the API key by making a simple API call"""
        try:
            genai.list_models()
            return True
        except Exception as e:
            print(f"Error: Invalid API key or API access issue: {e}")
            return False
    
    def list_stored_files(self) -> None:
        """List all files currently stored in Vertex AI"""
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
    
    def cleanup_stored_files(self) -> None:
        """Delete all files stored in Vertex AI"""
        print("Cleaning up all stored files …")
        try:
            files = list(genai.list_files())
            for f in files:
                genai.delete_file(name=f.name)
            print(f"  Deleted {len(files)} file{'s' if len(files)!=1 else ''}.")
        except Exception as e:
            print(f"Error during cleanup: {e}")
            sys.exit(1)
    
    def validate_file_size(self, file_path: str, max_size_mb: int = MAX_FILE_SIZE_MB) -> None:
        """Check if a file exceeds the maximum allowed size"""
        size_mb = Path(file_path).stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            raise ValueError(f"File {file_path} is too large ({size_mb:.1f}MB). Maximum size is {max_size_mb}MB.")
    
    def validate_input_files(self, args: argparse.Namespace) -> None:
        """Validate all input files exist and are within size limits"""
        # Validate ZIP files
        for zip_path in args.zip:
            if not Path(zip_path).exists():
                raise FileNotFoundError(f"ZIP not found: {zip_path}")
            self.validate_file_size(zip_path, max_size_mb=MAX_ZIP_SIZE_MB)
        
        # Validate user story file
        if not Path(args.story).exists():
            raise FileNotFoundError(f"Story not found: {args.story}")
        self.validate_file_size(args.story)
        
        # Validate acceptance criteria file if provided
        if args.criteria:
            if not Path(args.criteria).exists():
                raise FileNotFoundError(f"Criteria not found: {args.criteria}")
            self.validate_file_size(args.criteria)
        
        # Validate custom prompt file if provided
        if args.prompt:
            if not Path(args.prompt).exists():
                raise FileNotFoundError(f"Prompt not found: {args.prompt}")
            self.validate_file_size(args.prompt)
    
    def read_text_file(self, path: str) -> str:
        """Read content from a text file with proper error handling"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    raise ValueError(f"File is empty: {path}")
                return content
        except UnicodeDecodeError:
            print(f"Error: File {path} contains invalid UTF-8 characters")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file {path}: {e}")
            sys.exit(1)
    
    def upload_file(self, file_path: str) -> Any:
        """Upload a file to Vertex AI and wait for processing to complete"""
        name = Path(file_path).name
        print(f"Uploading {name} …")
        
        try:
            uploaded = genai.upload_file(file_path)
            retry_count = 0
            
            # Wait for file to be processed
            while uploaded.state.name == "PROCESSING" and retry_count < MAX_UPLOAD_RETRIES:
                print(f"  {name} state={uploaded.state.name}; retrying in {UPLOAD_RETRY_DELAY_SEC}s …")
                time.sleep(UPLOAD_RETRY_DELAY_SEC)
                uploaded = genai.get_file(name=uploaded.name)
                retry_count += 1
            
            if uploaded.state.name == "PROCESSING":
                raise Exception(f"Upload timed out after {MAX_UPLOAD_RETRIES} retries")
            if uploaded.state.name == "FAILED":
                raise Exception("Upload failed (state=FAILED)")
            
            print(f"  {name} is ACTIVE (URI: {uploaded.uri})")
            return uploaded
        except Exception as e:
            print(f"Error uploading {name}: {e}")
            raise
    
    def build_prompt(self, args: argparse.Namespace, uploaded_files: List[Any]) -> str:
        """Build the complete prompt for the AI model"""
        # Read input files
        story = self.read_text_file(args.story)
        criteria = self.read_text_file(args.criteria) if args.criteria else ""
        custom_prompt = self.read_text_file(args.prompt) if args.prompt else ""
        
        # System instruction
        system_inst = (
            "You are an expert QA engineer and senior software developer. "
            "Your task is to meticulously review the provided source code (in the uploaded ZIP file(s)) "
            "against the given user story and its acceptance criteria."
        )
        
        # Start with an empty user prompt
        user_prompt = ""
        
        # Process custom prompt with placeholders
        if custom_prompt:
            # Handle ZIP_FILES_LIST placeholder
            if "{ZIP_FILES_LIST}" in custom_prompt:
                zip_files_info = self._format_zip_files_list(uploaded_files)
                custom_prompt = custom_prompt.replace("{ZIP_FILES_LIST}", zip_files_info)
            
            # Handle user story and acceptance criteria placeholders
            custom_prompt = custom_prompt.replace("{USER_STORY}", story)
            if criteria:
                custom_prompt = custom_prompt.replace("{ACCEPTANCE_CRITERIA}", criteria)
            else:
                custom_prompt = custom_prompt.replace(
                    "{ACCEPTANCE_CRITERIA}",
                    "(The acceptance criteria are likely embedded within or implied by the user story. "
                    "Please infer them as best as possible.)"
                )
            
            # Handle file-specific placeholders
            custom_prompt = self._replace_file_placeholders(custom_prompt, uploaded_files)
            
            # Add custom prompt to user prompt
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
                user_prompt += (
                    "\n(The acceptance criteria are likely embedded within or implied by the user story. "
                    "Please infer them as best as possible.)\n"
                )
        
        return f"{system_inst}\n\n{user_prompt}"
    
    def _format_zip_files_list(self, uploaded_files: List[Any]) -> str:
        """Format the list of ZIP files for the prompt"""
        zip_files_info = ""
        for i, uploaded in enumerate(uploaded_files, 1):
            display_name = self.file_display_names.get(uploaded.name, "Unknown")
            zip_files_info += f"""
ZIP File #{i}:
  File Name on Server: {uploaded.name}
  Display Name: {display_name}
  URI for Model Access: {uploaded.uri}
"""
        return zip_files_info
    
    def _replace_file_placeholders(self, prompt: str, uploaded_files: List[Any]) -> str:
        """Replace file-specific placeholders in the prompt"""
        for i, uploaded in enumerate(uploaded_files, 1):
            display_name = self.file_display_names.get(uploaded.name, "Unknown")
            
            # Use indexed placeholders for multiple files
            prompt = prompt.replace(f"{{FILE_NAME_{i}}}", uploaded.name)
            prompt = prompt.replace(f"{{DISPLAY_NAME_{i}}}", display_name)
            prompt = prompt.replace(f"{{FILE_URI_{i}}}", uploaded.uri)
            
            # Also replace non-indexed placeholders with the first file (for backward compatibility)
            if i == 1:
                prompt = prompt.replace("{FILE_NAME}", uploaded.name)
                prompt = prompt.replace("{DISPLAY_NAME}", display_name)
                prompt = prompt.replace("{FILE_URI}", uploaded.uri)
        
        return prompt
    
    def generate_review(self, prompt: str) -> str:
        """Generate a review using the Gemini AI model"""
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            generation_config=genai.GenerationConfig(temperature=0.2),  # Lower temperature for more focused code reviews
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT",       "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH",      "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
        )
        
        print(f"\nSending request to {MODEL_NAME} …")
        
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error generating review: {e}")
            raise
    
    def save_feedback(self, feedback: str, output_path: str) -> None:
        """Save feedback to a file"""
        try:
            with open(output_path, 'w', encoding='utf-8') as out:
                out.write(feedback)
            print(f"\nFeedback saved to: {output_path}")
        except Exception as e:
            print(f"Error saving feedback: {e}")
            raise
    
    def cleanup_uploaded_files(self) -> None:
        """Delete all uploaded files"""
        for uploaded in self.uploaded_files:
            try:
                display_name = self.file_display_names.get(uploaded.name, "Unknown")
                genai.delete_file(name=uploaded.name)
                print(f"Deleted {display_name}")
            except Exception as e:
                print(f"Error deleting {display_name}: {e}")
    
    def run_review(self, args: argparse.Namespace) -> None:
        """Run the complete review process"""
        try:
            # Validate API key
            if not self.validate_api_key():
                sys.exit(1)
            
            # Validate input files
            self.validate_input_files(args)
            
            # Upload all ZIP files
            for zip_path in args.zip:
                uploaded = self.upload_file(zip_path)
                self.uploaded_files.append(uploaded)
                self.file_display_names[uploaded.name] = Path(zip_path).name
            
            # Build the prompt
            full_prompt = self.build_prompt(args, self.uploaded_files)
            
            # Show or save prompt if requested
            if args.show_prompt:
                print("\n--- Full Prompt ---\n")
                print(full_prompt)
                print("\n--- End Full Prompt ---\n")
            
            if args.save_prompt:
                with open(args.save_prompt, 'w', encoding='utf-8') as prompt_file:
                    prompt_file.write(full_prompt)
                print(f"Full prompt saved to: {args.save_prompt}")
            
            # Generate review
            feedback = self.generate_review(full_prompt)
            
            # Save feedback to file if output path is provided
            if args.output:
                self.save_feedback(feedback, args.output)
            
            # Show feedback if requested
            if args.show_feedback:
                print("\n--- Feedback ---\n")
                print(feedback)
                print("\n--- End Feedback ---")
            
        except Exception as e:
            print(f"\nError: {e}")
            sys.exit(1)
        finally:
            # Clean up uploaded files unless --keep-files is specified
            if not args.keep_files:
                self.cleanup_uploaded_files()
            else:
                print("Keeping uploaded files (--keep-files specified)")
            
            # Always list remaining files
            self.list_stored_files()


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Gemini PR Reviewer: analyze code or manage stored files, always list remaining."
    )
    
    # File inputs
    parser.add_argument("-z", "--zip",      help="Path to project ZIP file(s)", nargs='+')
    parser.add_argument("-s", "--story",    help="Path to user story text file")
    parser.add_argument("-c", "--criteria", help="Path to acceptance criteria text file")
    parser.add_argument("-p", "--prompt",   help="Path to custom user prompt text file")
    parser.add_argument("-o", "--output",   help="Path to save feedback markdown")
    
    # Display options
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
    
    # File management options
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
    
    # Version info
    parser.add_argument("--version", action="version", version="1.0.0")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not (args.list_files or args.cleanup_files) and not (args.zip and args.story and args.prompt):
        parser.error("For review you must provide -z/--zip, -s/--story, and -p/--prompt")
    
    # Resolve paths to absolute paths
    if args.zip:
        args.zip = [str(Path(z).resolve()) for z in args.zip]
    if args.story:
        args.story = str(Path(args.story).resolve())
    if args.criteria:
        args.criteria = str(Path(args.criteria).resolve())
    if args.prompt:
        args.prompt = str(Path(args.prompt).resolve())
    if args.output:
        args.output = str(Path(args.output).resolve())
    if args.save_prompt:
        args.save_prompt = str(Path(args.save_prompt).resolve())
    
    return args


def main() -> None:
    """Main entry point for the script"""
    args = parse_arguments()
    reviewer = GeminiReviewer()
    
    if args.list_files:
        reviewer.list_stored_files()
        sys.exit(0)
    
    if args.cleanup_files:
        reviewer.cleanup_stored_files()
        reviewer.list_stored_files()
        sys.exit(0)
    
    reviewer.run_review(args)


if __name__ == "__main__":
    main()
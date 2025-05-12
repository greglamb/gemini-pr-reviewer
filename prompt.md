**Source Code:**
The complete source code for the project/feature is provided in the uploaded ZIP files:

{ZIP_FILES_LIST}

**Before and After**

- before.zip contains the complete source code before work began on this user story.
- after.zip contains the complete source code after work was allegedly completed on this user story.
- after.zip contains the source included in the pull request.
- Please help me determine if this pull request is ready to be merged, and this user story is ready to be closed.

**Your Task:**
1. Thoroughly analyze the source code accessible via the provided file URI(s).
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

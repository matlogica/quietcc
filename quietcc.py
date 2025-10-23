#!/usr/bin/env python3

import sys
import subprocess
import re
import os
import uuid
import shlex

# --- Configuration ---
CONTEXT_LINES = 50 # For source code snippets
ERROR_CONTEXT_LINES = 40 # Lines *after* the first error line in compiler output
ERROR_REPORT_DIR = "." # Directory to save error reports

# Default compiler - you can change this to your preferred compiler
DEFAULT_COMPILER = "g++"

# --- Helper Functions ---
def find_error_locations(text):
    """
    Parses compiler output text to find file paths, line numbers, and error messages.
    Returns a list of tuples: (filepath, line_number, error_line_text)
    """
    error_pattern = re.compile(r"^((?:[a-zA-Z]:\\|\.\.?[/\\])?[^:\n]+?):(\d+):(?:(?:\d+:)?\s*(?:fatal\s+)?error:\s*.*)$", re.MULTILINE)
    locations = []
    unique_locs = set()

    for match in error_pattern.finditer(text):
        filepath = match.group(1).strip()
        try:
            line_num = int(match.group(2))
            error_line = match.group(0).strip()
            abs_filepath = os.path.abspath(filepath)
            loc_key = (abs_filepath, line_num) # Use tuple of (abs_path, line_num) for uniqueness
            if loc_key not in unique_locs:
                 # Store original path for display, line number, and the error line itself
                 locations.append((filepath, line_num, error_line)) 
                 unique_locs.add(loc_key)
        except ValueError:
            continue
        except Exception as e:
            print(f"Error processing match '{match.group(0)}': {e}", file=sys.stderr)
    return locations

def read_code_snippet(filepath, line_number, context=CONTEXT_LINES):
    """
    Reads source code file and extracts lines around the specified line number.
    Returns a formatted string of the code snippet or an error message.
    """
    try:
        abs_filepath = os.path.abspath(filepath)
        if not os.path.exists(abs_filepath):
            return f"    <File not found: {filepath} (abs: {abs_filepath})>\n"

        with open(abs_filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        start_line = max(0, line_number - context - 1)
        end_line = min(len(lines), line_number + context)

        snippet_lines = []
        for i in range(start_line, end_line):
            line_num_display = i + 1
            prefix = "  >>" if line_num_display == line_number else "    "
            snippet_lines.append(f"{prefix}{line_num_display:>{5}}: {lines[i].rstrip()}")

        if not snippet_lines:
             return f"    <Could not read lines around {line_number} in {filepath}>\n"
        return "\n".join(snippet_lines) + "\n"
    except FileNotFoundError:
        return f"    <File not found: {filepath} (abs: {abs_filepath})>\n"
    except Exception as e:
        return f"    <Error reading file {filepath}: {e}>\n"

def filter_compiler_output(output_text, context_after_error=ERROR_CONTEXT_LINES):
    """
    Filters compiler output. Finds the first 'error:' line and includes
    that line plus the next 'context_after_error' lines.
    Lines containing 'warning:' are removed from this block.
    If no 'error:' line is found, it keeps all non-warning lines.
    """
    lines = output_text.splitlines()
    first_error_index = -1
    for i, line in enumerate(lines):
        if "error:" in line.lower():
            first_error_index = i
            break

    filtered_lines = []
    if first_error_index != -1:
        start_index = first_error_index
        end_index = first_error_index + 1 + context_after_error
        context_block = lines[start_index:end_index]
        for line in context_block:
            if "warning:" not in line.lower():
                filtered_lines.append(line)
    else:
        for line in lines:
             if "warning:" not in line.lower():
                filtered_lines.append(line)
    return "\n".join(filtered_lines)


# --- Main Execution ---

if __name__ == "__main__":
    # Check if we're being used as a compiler wrapper (no explicit compiler specified)
    if len(sys.argv) < 2:
        print("Usage: error_analyzer.py <compiler> [compiler_args...]", file=sys.stderr)
        print("   OR: Set as CXX compiler wrapper (uses default compiler)", file=sys.stderr)
        sys.exit(1)
    
    # If first argument looks like a compiler flag, we're being used as a compiler wrapper
    if sys.argv[1].startswith('-'):
        # Use default compiler with all arguments
        compiler_cmd = DEFAULT_COMPILER
        compiler_args = sys.argv[1:]  # All arguments are compiler args
    else:
        # Original behavior: first arg is compiler, rest are args
        compiler_cmd = sys.argv[1]
        compiler_args = sys.argv[2:]
    
    full_command = [compiler_cmd] + compiler_args

    source_files_in_command = []
    source_extensions = ('.cpp', '.cxx', '.cc', '.c')
    for arg in compiler_args:
        if isinstance(arg, str) and arg.lower().endswith(source_extensions) and not arg.startswith('-'):
             source_files_in_command.append(os.path.abspath(arg))

    try:
        process = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            check=False
        )

        # Always capture output and create report (for both success and failure)
        combined_output = process.stdout + process.stderr
        
        if process.returncode == 0:
            # Success case - still create a report but simpler
            report_basename = f"compile-success-{uuid.uuid4().hex[:10]}.txt"
            report_filename = os.path.join(ERROR_REPORT_DIR, report_basename)
            full_report_path = os.path.abspath(report_filename)
            
            os.makedirs(ERROR_REPORT_DIR, exist_ok=True)
            
            try:
                with open(report_filename, 'w', encoding='utf-8') as report_file:
                    safe_command_str = shlex.join(full_command)
                    report_file.write(f"Command:\n{safe_command_str}\n\n")
                    report_file.write("="*20 + " COMPILATION SUCCESSFUL " + "="*20 + "\n")
                    if combined_output.strip():
                        report_file.write("Compiler Output:\n")
                        report_file.write(combined_output.strip() + "\n\n")
                    else:
                        report_file.write("No compiler output.\n\n")
                        
                    if source_files_in_command:
                        report_file.write(f"Source Files: {', '.join(source_files_in_command)}\n")
                
                # Don't print anything to console for successful compilation
                sys.exit(0)
                
            except Exception as write_e:
                # If we can't write the report, fall back to console output
                if process.stdout:
                    print(process.stdout, end='')
                if process.stderr:
                    print(process.stderr, end='', file=sys.stderr)
                sys.exit(0)
        else:
            # Failure case - create detailed error report
            combined_output = process.stdout + process.stderr
            filtered_errors = filter_compiler_output(combined_output, ERROR_CONTEXT_LINES)
            error_locations = find_error_locations(combined_output) # Use full output
            num_errors = len(error_locations)

            report_basename = f"error-{uuid.uuid4().hex[:10]}.txt"
            report_filename = os.path.join(ERROR_REPORT_DIR, report_basename)
            full_report_path = os.path.abspath(report_filename)

            os.makedirs(ERROR_REPORT_DIR, exist_ok=True)

            try:
                with open(report_filename, 'w', encoding='utf-8') as report_file:
                    safe_command_str = shlex.join(full_command)
                    report_file.write(f"Command:\n{safe_command_str}\n\n")
                    report_file.write("="*20 + " Filtered Compiler Output (First Error + Context) " + "="*20 + "\n")
                    report_file.write(filtered_errors.strip() + "\n\n")

                    if error_locations:
                        report_file.write("="*20 + " Relevant Source Code Snippets (From All Errors) " + "="*20 + "\n")
                        for filepath, line_num, error_line_text in error_locations:
                            report_file.write(f"\n--- Snippet for error at: {filepath}:{line_num} ---\n")
                            report_file.write(f"    Error Message: {error_line_text}\n")
                            snippet = read_code_snippet(filepath, line_num, CONTEXT_LINES)
                            report_file.write(snippet)
                    else:
                         report_file.write("="*20 + " No specific file:line:error patterns found in output " + "="*20 + "\n")

                print("========================================", file=sys.stderr)
                print(f"Compilation failed (exit code {process.returncode}).", file=sys.stderr)
                print(f"  Report: {full_report_path}", file=sys.stderr)
                if source_files_in_command:
                    print(f"  Source(s) in Command: {', '.join(source_files_in_command)}", file=sys.stderr)
                print(f"  Errors Found (file:line:error pattern): {num_errors}", file=sys.stderr)
                print("========================================", file=sys.stderr)

                # Don't output to console - everything is in the report
                # Build tools will see the non-zero exit code

            except Exception as write_e:
                print("========================================", file=sys.stderr)
                print(f"Compilation failed (exit code {process.returncode}).", file=sys.stderr)
                print(f"  Attempted Report: {full_report_path}", file=sys.stderr)
                if source_files_in_command:
                   print(f"  Source(s) in Command: {', '.join(source_files_in_command)}", file=sys.stderr)
                print(f"  Errors Found (file:line:error pattern): {num_errors}", file=sys.stderr)
                print(f"  ERROR WRITING REPORT FILE: {write_e}", file=sys.stderr)
                print("========================================", file=sys.stderr)

            sys.exit(process.returncode)

    except FileNotFoundError:
        print(f"Error: Compiler '{compiler_cmd}' not found.", file=sys.stderr)
        print("Ensure the compiler is in your PATH or provide the full path.", file=sys.stderr)
        sys.exit(127)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
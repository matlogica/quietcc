#!/usr/bin/env python3

"""
C++ Compiler Error Message Parser

Parses error messages from MSVC, GCC, and Clang compilers.
Extracts error locations, messages, and trigger locations (call stacks).
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import sys
import subprocess
import os
import uuid
import shlex
import platform

ERROR_REPORT_DIR = "." # Directory to save error reports
SNIP_RADIUS = 25
NUM_ERROR_PRE_LINES = 3
NUM_ERROR_POST_LINES = 6


# Default compiler - you can change this to your preferred compiler
# Detects platform: 'cl' for Windows, 'g++' for Unix-like systems
DEFAULT_COMPILER = "cl" if platform.system() == "Windows" else "g++"

class CompilerType(Enum):
    """Supported compiler types"""
    MSVC = "msvc"
    GCC = "gcc"
    CLANG = "clang"
    UNKNOWN = "unknown"


@dataclass
class Location:
    """Represents a source code location"""
    file_path: str
    line_number: int
    error_line: int # line number in compiler output where this location was found
    
    def __repr__(self):
        return f"{self.file_path}:{self.line_number} @ ({self.error_line})"


@dataclass
class Error:
    """Represents a compiler error with its locations"""
    message: str
    error_location: Location
    trigger_locations: List[Location] = field(default_factory=list)
    
    def __repr__(self):
        triggers = " -> ".join(str(loc) for loc in self.trigger_locations)
        if triggers:
            return f"Error at {self.error_location}: {self.message}\n  Trigger chain: {triggers}"
        return f"Error at {self.error_location}: {self.message}"


class CompilerErrorParser:
    """Parser for C++ compiler error messages"""
    
    # MSVC patterns
    MSVC_ERROR_PATTERN = re.compile(
        r'^(.+?)\((\d+)\):\s*(?:error)\s+[A-Z]\d+:\s*(.+)$',
        re.MULTILINE
    )
    MSVC_NOTE_PATTERN = re.compile(
        r'^(.+?)\((\d+)\):\s*note:\s*(.+)$',
        re.MULTILINE
    )
    
    # GCC patterns
    GCC_ERROR_PATTERN = re.compile(
        r'^(.+?):(\d+):(?:\d+:)?\s*(?:error):\s*(.+?)(?:\s*\[.*?\])?$',
        re.MULTILINE
    )
    GCC_NOTE_PATTERN = re.compile(
        r'^(.+?):(\d+):(?:\d+:)?\s*note:\s*(.+)$',
        re.MULTILINE
    )
    GCC_CONTEXT_PATTERN = re.compile(
        r'^(.+?):\s*In (?:instantiation|function|member function|expansion)\s+(?:of|from)\s+',
        re.MULTILINE
    )
    
    # Clang patterns
    CLANG_ERROR_PATTERN = re.compile(
        r'^(.+?):(\d+):(?:\d+:)?\s*(?:error):\s*(.+)$',
        re.MULTILINE
    )
    CLANG_NOTE_PATTERN = re.compile(
        r'^(.+?):(\d+):(?:\d+:)?\s*note:\s*(.+)$',
        re.MULTILINE
    )
    
    def __init__(self):
        self.errors: List[Error] = []
        self.compiler_type: CompilerType = CompilerType.UNKNOWN
    
    def detect_compiler(self, output: str) -> CompilerType:
        """Detect which compiler generated the output"""
        if "Microsoft (R) C/C++ Optimizing Compiler" in output:
            return CompilerType.MSVC
        elif "error generated" in output or "errors generated" in output:
            return CompilerType.CLANG
        elif "cc1plus:" in output or output.count(": note:") > 0:
            # GCC often has cc1plus messages or lots of notes
            return CompilerType.GCC
        return CompilerType.UNKNOWN
    
    def parse(self, compiler_output: str) -> List[Error]:
        """
        Parse compiler output and return list of errors.
        
        Args:
            compiler_output: Raw compiler output string
            
        Returns:
            List of Error objects
        """
        self.errors = []
        self.compiler_type = self.detect_compiler(compiler_output)
        
        if self.compiler_type == CompilerType.MSVC:
            self._parse_msvc(compiler_output)
        elif self.compiler_type == CompilerType.GCC:
            self._parse_gcc(compiler_output)
        elif self.compiler_type == CompilerType.CLANG:
            self._parse_clang(compiler_output)
        else:
            # Try all parsers
            self._parse_msvc(compiler_output)
            if not self.errors:
                self._parse_gcc(compiler_output)
            if not self.errors:
                self._parse_clang(compiler_output)
        
        return self.errors
    
    def _parse_msvc(self, output: str) -> None:
        """Parse MSVC compiler output"""
        lines = output.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Check for error line
            error_match = self.MSVC_ERROR_PATTERN.match(line)
            if error_match:
                file_path = error_match.group(1)
                line_number = int(error_match.group(2))
                message = error_match.group(3)
                
                error_location = Location(file_path, line_number, i)
                trigger_locations = []
                
                # Look ahead for notes that provide context
                j = i + 1
                while j < len(lines):
                    note_line = lines[j].strip()
                    note_match = self.MSVC_NOTE_PATTERN.match(note_line)
                    
                    if note_match:
                        note_file = note_match.group(1)
                        note_line_num = int(note_match.group(2))
                        note_text = note_match.group(3)
                        
                        # Add notes as trigger locations
                        # MSVC shows instantiation context from oldest to newest
                        trigger_locations.append(Location(note_file, note_line_num, j))
                        j += 1
                    elif self.MSVC_ERROR_PATTERN.match(note_line):
                        # Hit next error, stop
                        break
                    else:
                        j += 1
                        # Continue looking for notes within a reasonable distance
                        if j - i > 30:
                            break
                
                self.errors.append(Error(
                    message=message,
                    error_location=error_location,
                    trigger_locations=trigger_locations
                ))
                i = j
                continue
            
            i += 1
    
    def _parse_gcc(self, output: str) -> None:
        """Parse GCC compiler output"""
        lines = output.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Check for error line
            error_match = self.GCC_ERROR_PATTERN.match(line)
            if error_match:
                file_path = error_match.group(1)
                line_number = int(error_match.group(2))
                message = error_match.group(3)
                
                error_location = Location(file_path, line_number, i)
                trigger_locations = []
                
                # Look BACKWARD for instantiation context lines
                # GCC prints "required from" lines before the error
                j = i - 1
                context_lines = []
                while j >= 0 and j >= i - 30:
                    prev_line = lines[j].strip()
                    
                    # Check if this line contains instantiation context
                    # Match both "required from" and other location patterns
                    req_match = re.match(r'^(.+?):(\d+):\d+:\s+required from', prev_line)
                    if req_match:
                        context_lines.insert(0, Location(
                            req_match.group(1),
                            int(req_match.group(2)),
                            j
                        ))
                    elif 'In instantiation of' in prev_line or 'In function' in prev_line:
                        # This marks the start of the instantiation chain
                        break
                    
                    j -= 1
                
                trigger_locations.extend(context_lines)
                
                # Look ahead for notes and additional context
                j = i + 1
                while j < len(lines):
                    note_line = lines[j].strip()
                    
                    # Check for note lines that provide instantiation context
                    note_match = self.GCC_NOTE_PATTERN.match(note_line)
                    if note_match:
                        note_file = note_match.group(1)
                        note_line_num = int(note_match.group(2))
                        note_text = note_match.group(3)
                        
                        # GCC notes show various contexts:
                        # - "required from" chains (template instantiation)
                        # - "in expansion of" (macro expansion)
                        # - "in definition of macro" (macro definition location)
                        if ("required from" in note_text or 
                            "in expansion of" in note_text or
                            "in definition of macro" in note_text):
                            trigger_locations.append(Location(note_file, note_line_num, j))
                        
                        j += 1
                    elif self.GCC_ERROR_PATTERN.match(note_line):
                        # Hit next error, stop
                        break
                    else:
                        j += 1
                        if j - i > 30:
                            break
                
                self.errors.append(Error(
                    message=message,
                    error_location=error_location,
                    trigger_locations=trigger_locations
                ))
                i = j
                continue
            
            i += 1
    
    def _parse_clang(self, output: str) -> None:
        """Parse Clang compiler output"""
        lines = output.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Check for error line
            error_match = self.CLANG_ERROR_PATTERN.match(line)
            if error_match:
                file_path = error_match.group(1)
                line_number = int(error_match.group(2))
                message = error_match.group(3)
                
                error_location = Location(file_path, line_number, i)
                trigger_locations = []
                
                # Look ahead for notes
                j = i + 1
                while j < len(lines):
                    note_line = lines[j].strip()
                    note_match = self.CLANG_NOTE_PATTERN.match(note_line)
                    
                    if note_match:
                        note_file = note_match.group(1)
                        note_line_num = int(note_match.group(2))
                        note_text = note_match.group(3)
                        
                        # Clang notes show instantiation/expansion chain
                        if ("in instantiation" in note_text or 
                            "expanded from" in note_text or
                            "requested here" in note_text):
                            trigger_locations.append(Location(note_file, note_line_num, j))
                        
                        j += 1
                    elif self.CLANG_ERROR_PATTERN.match(note_line):
                        # Hit next error, stop
                        break
                    else:
                        j += 1
                        if j - i > 30:
                            break
                
                self.errors.append(Error(
                    message=message,
                    error_location=error_location,
                    trigger_locations=trigger_locations
                ))
                i = j
                continue
            
            i += 1


def parse_compiler_errors(compiler_output: str) -> List[Error]:
    """
    Convenience function to parse compiler errors.
    
    Args:
        compiler_output: Raw compiler output string
        
    Returns:
        List of Error objects
    """
    parser = CompilerErrorParser()
    return parser.parse(compiler_output)


class TextBlockRange:
    """Helper class to represent a range of text lines"""
    def __init__(self, start_line: int, end_line: int):
        self.start_line = start_line
        self.end_line = end_line
    
    def __repr__(self):
        return f"TextBlockRange({self.start_line}, {self.end_line})"


def add_text_block_range(ranges: List[TextBlockRange], TextBlock: TextBlockRange) -> List[TextBlockRange]:
    # if TextBlock overlaps or is adjacent to any existing range, merge them
    ranges_sorted = sorted(ranges + [TextBlock], key=lambda r: r.start_line)
    merged_ranges = []
    current_range = ranges_sorted[0]
    for r in ranges_sorted[1:]:
        if r.start_line <= current_range.end_line:
            # Overlaps or adjacent, merge
            current_range.end_line = max(current_range.end_line, r.end_line)
        else:
            merged_ranges.append(current_range)
            current_range = r
    merged_ranges.append(current_range)
    return merged_ranges

# Example usage and testing
def generate_report(compiler_output: str):

    compiler_output_ranges = []

    source_code_blocks = {}  # map from file_path to list of TextBlockRange

#    print("Merged Ranges:", merged)

    errors = parse_compiler_errors(compiler_output)

    for error in errors:
        if error.error_location.file_path not in source_code_blocks:
            source_code_blocks[error.error_location.file_path] = []
        source_code_blocks[error.error_location.file_path] = add_text_block_range(
            source_code_blocks[error.error_location.file_path],
            TextBlockRange(max(0, error.error_location.line_number - SNIP_RADIUS), error.error_location.line_number + SNIP_RADIUS)
        )
        compiler_output_ranges = add_text_block_range(
            compiler_output_ranges,
            TextBlockRange(max(0, error.error_location.error_line - NUM_ERROR_PRE_LINES), error.error_location.error_line + NUM_ERROR_POST_LINES)
        )
        for trigger in error.trigger_locations:
            if trigger.file_path not in source_code_blocks:
                source_code_blocks[trigger.file_path] = []
            source_code_blocks[trigger.file_path] = add_text_block_range(
                source_code_blocks[trigger.file_path],
                TextBlockRange(max(0, trigger.line_number - SNIP_RADIUS), trigger.line_number + SNIP_RADIUS)
            )
            compiler_output_ranges = add_text_block_range(
                compiler_output_ranges,
                TextBlockRange(max(0, trigger.error_line - NUM_ERROR_PRE_LINES), trigger.error_line + NUM_ERROR_POST_LINES)
            )
        # calc number of lines in report
        total_report_lines = sum(r.end_line - r.start_line for r in compiler_output_ranges)
        # calc number of lines in source code snippets
        for file_path, ranges in source_code_blocks.items():
            total_report_lines += sum(r.end_line - r.start_line for r in ranges)

        if total_report_lines > 500:
            break

#    print(f"Total report lines: {total_report_lines}")

    report_lines = []
    output_lines = compiler_output.split('\n')
    for r in compiler_output_ranges:
        report_lines.extend(output_lines[r.start_line:r.end_line])

    for file_path, ranges in source_code_blocks.items():
#        print(f"Source code snippets from {file_path}:")
        try:
            with open(file_path, 'r') as f:
                source_lines = f.readlines()
                # trim
                source_lines = [line.rstrip() for line in source_lines]
                for r in ranges:
                    report_lines.append(f"\n// Source code from {file_path} lines {r.start_line + 1} to {r.end_line}:\n")
                    for line_i in range(r.start_line, r.end_line):
                        if line_i >= len(source_lines):
                            break
                        line_with_number = f"{line_i + 1}: {source_lines[line_i]}"
                        report_lines.append(line_with_number)
                    
        except Exception as e:
            print(f"Could not read file {file_path}: {e}")  

    return ["\n".join(report_lines), errors]


# if __name__ == "__main__":
#     # read from stdin
#     import sys
#     compiler_output = sys.stdin.read()
#     errors = parse_compiler_errors(compiler_output)
#     for error in errors:
#         print(error)

#     report = generate_report(compiler_output)

#     print("\n=== Generated Report ===\n")
#     print(report)


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
    binary_files_in_command = []
    binary_extensions = ('.o', '.obj')
    for arg in compiler_args:
        if isinstance(arg, str) and arg.lower().endswith(binary_extensions) and not arg.startswith('-'):
                binary_files_in_command.append(os.path.abspath(arg))
    # unique binary_extensions
    binary_files_in_command = list(set(binary_files_in_command))
    cwd = os.getcwd()
    # remove cwd from binary_files_in_command for display
    binary_files_in_command = [os.path.relpath(f, cwd) for f in binary_files_in_command]

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

            report_basename = f"error-{uuid.uuid4().hex[:10]}.txt"
            if source_files_in_command:
                # report_basename is a has of all source files
                source_files_str = "_".join([os.path.basename(f) for f in source_files_in_command])
                md5_hash = uuid.uuid5(uuid.NAMESPACE_DNS, source_files_str).hex[:10]
                report_basename = f"error-{md5_hash}.txt"

            report_filename = os.path.join(ERROR_REPORT_DIR, report_basename)
            full_report_path = os.path.abspath(report_filename)


            [report, errors] = generate_report(combined_output)

            os.makedirs(ERROR_REPORT_DIR, exist_ok=True)

            try:
                with open(report_filename, 'w', encoding='utf-8') as report_file:
                    safe_command_str = shlex.join(full_command)
                    report_file.write(f"Command:\n{safe_command_str}\n\n")
                    report_file.write("="*20 + " Filtered Compiler Output (First Error + Context) " + "="*20 + "\n")
                    report_file.write(report)

                print("========================================", file=sys.stderr)
                print(f"Compilation failed (exit code {process.returncode}).", file=sys.stderr)
                print(f"  Report: {full_report_path}", file=sys.stderr)
                # first error location:
                if errors:
                    first_error = errors[0]
                    # print(f"  First Error Location: {first_error.error_location}:{first_error.trigger_locations}", file=sys.stderr)
                    # # output first 4 error locations
                    for i in range(0, min(5, len(errors))):
#                        print(f"  Additional Error Location: {error_locations[i][0]}:{error_locations[i][1]}", file=sys.stderr)
                        error = errors[i]
                        first_and_last_locations_str = ""
                        if len(error.trigger_locations) > 0:
                            first_loc = error.trigger_locations[0]
                            last_loc = error.trigger_locations[-1]
                            if first_loc.file_path == last_loc.file_path and first_loc.line_number == last_loc.line_number:
                                first_and_last_locations_str = f" -> {first_loc.file_path}:{first_loc.line_number}"
                            else:
                                first_and_last_locations_str = f" -> {first_loc.file_path}:{first_loc.line_number} ... {last_loc.file_path}:{last_loc.line_number}"


                        print(f"  Error {i+1}: {errors[i].error_location.file_path}:{errors[i].error_location.line_number} {first_and_last_locations_str}", file=sys.stderr)
                if source_files_in_command:
                    print(f"  Source(s) in Command: {', '.join(source_files_in_command)}", file=sys.stderr)
                if binary_files_in_command:
                    print(f"  Binary(s) in Command: {', '.join(binary_files_in_command)}", file=sys.stderr)
                print(f"  Errors Found: {len(errors)}", file=sys.stderr)
                print("========================================", file=sys.stderr)

            # print("\n=== Generated Report ===\n")
            # print(report)
            except Exception as write_e:
                print("========================================", file=sys.stderr)
                print(f"Compilation failed (exit code {process.returncode}).", file=sys.stderr)
                print(f"  Attempted Report: {full_report_path}", file=sys.stderr)
                if source_files_in_command:
                   print(f"  Source(s) in Command: {', '.join(source_files_in_command)}", file=sys.stderr)
                if binary_files_in_command:
                   print(f"  Binary(s) in Command: {', '.join(binary_files_in_command)}", file=sys.stderr)
                print(f"  Errors Found (file:line:error pattern): {len(errors)}", file=sys.stderr)
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

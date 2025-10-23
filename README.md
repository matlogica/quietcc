# Error Analyzer for C++ Compiler

A tool that analyzes and categorizes error messages produced by C++ compilers, helping developers filter warning noise and focus on critical compilation errors.

## The Problem

When using build tools like `ninja` or `make`:
- Errors and warnings appear mixed in console output
- Parallel compilation produces jumbled, hard-to-read output
- When errors occur, developers often must restart builds with single-threaded mode to see clear compiler output
- Template-heavy C++ error messages are especially difficult to comprehend

## The Solution

This tool:
- **Captures** compiler output during builds
- **Filters** out warnings to focus on errors
- **Extracts** relevant source code snippets around error locations
- **Saves** categorized errors to individual files
- **Provides** clean, LLM-ready reports for getting fix suggestions

## Installation

1. Download `quietcc.py` to your preferred location
2. Make it executable:
   ```bash
   chmod +x /path/to/quietcc.py
   ```

## Usage

### Method 1: Direct Invocation
```bash
./quietcc.py g++ myfile.cpp -o myfile
```

### Method 2: As a Compiler Wrapper (Recommended)
Set the `CXX` environment variable with your compiler and run your build as usual.:

```bash
CXX="/path/to/quietcc.py g++" cmake ..
cmake --build .
# or
ninja
# or
make
```

### What You'll See

**On successful compilation:** Silent operation (no console output)

**On compilation failure:**
```
========================================
Compilation failed (exit code 1).
  Report: /opt/project/build/error-7588f59011.txt
  Source(s) in Command: /opt/project/src/template_test.cpp
  Errors Found (file:line:error pattern): 1
========================================
```

## Output Format

Error reports contain:
1. **Command** - The exact compiler invocation
2. **Filtered Compiler Output** - First error with context (no warnings)
3. **Source Code Snippets** - Code around each error location with line numbers

## Example Use Case

See the complete example below demonstrating how to use this tool with complex template errors and get LLM assistance for fixes.

## Complete Workflow Example

```
bash
./quietcc.py g++ -std=c++14 template_error_example.cpp -o template_test
```

**Output:**
```
========================================
Compilation failed (exit code 1).
  Report: /home/dev/EA/error-b2f578d0ab.txt
  Source(s) in Command: /home/dev/EA/template_error_example.cpp
  Errors Found (file:line:error pattern): 1
========================================
```

See the generated report file [`error-b2f578d0ab.txt`](error-b2f578d0ab.txt) for detailed error context.

## Configuration

You can customize the tool by editing these variables in `quietcc.py`:

- `CONTEXT_LINES` (default: 50) - Lines of source code shown around each error
- `ERROR_CONTEXT_LINES` (default: 40) - Lines of compiler output after first error
- `ERROR_REPORT_DIR` (default: ".") - Directory for error report files
- `DEFAULT_COMPILER` (default: "g++") - Compiler to use in wrapper mode

## License

This tool is provided as-is for developer use.
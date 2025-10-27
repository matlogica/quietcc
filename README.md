# Error Analyzer for C++ Compiler

A tool that analyzes and categorizes error messages produced by C++ compilers, helping developers filter warning noise and focus on critical compilation errors. Ignoring warnings isn't ideal programming practice, but often it's not possible to fix someone else's legacy code. Or be strict and [Enable Warnings as Errors](#warnings-as-errors) in your own projects to catch new issues early.

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
Use cmake CMAKE_CXX_COMPILER_LAUNCHER option.

```bash
cmake .. -DCMAKE_CXX_COMPILER_LAUNCHER=/path/to/quietcc.py
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
  Report: /opt/project/build/error-d5cb7ee915.txt
  Error 1: /opt/project/src/LiborMarketModel.h:154 
  Source(s) in Command: /opt/project/src/lmm_test_data.cpp
  Binary(s) in Command: examples/LMM/CMakeFiles/lmm_test.dir/lmm_test_data.cpp.o
  Errors Found: 1
========================================
```

**Multiple errors show with numbered entries:**
```
========================================
Compilation failed (exit code 1).
  Report: /opt/project/build/error-bc24ccad57.txt
  Error 1: /opt/project/examples/LMM/LiborMarketModel.h:154 
  Error 2: /opt/project/examples/LMM/Template.h:89 -> /opt/project/src/main.cpp:45
  Error 3: /opt/project/src/utils.cpp:120 
  Source(s) in Command: /opt/project/examples/LMM/lmm_test.cpp
  Binary(s) in Command: examples/LMM/CMakeFiles/lmm_test.dir/lmm_test.cpp.o
  Errors Found: 3
========================================
```

**Note:** When compilation fails due to linker errors or unrecognized diagnostics, you'll see:
```
========================================
Compilation failed (exit code 1).
  Report: /opt/project/build/error-f77e52a9a3.txt
  Source(s) in Command: /opt/project/examples/main.cpp
  Binary(s) in Command: examples/CMakeFiles/example.dir/main.cpp.o
  Errors Found: 0
========================================
```
"Errors Found: 0" means no structured compiler errors were detected, but the report file still contains the complete compiler output for debugging.

## Output Format

Error reports contain:
1. **Command** - The exact compiler invocation
2. **Filtered Compiler Output** - First error with context (no warnings)
3. **Source Code Snippets** - Code around each error location with line numbers

### Console Output Fields

When compilation fails, the tool displays:
- **Report:** Full path to the detailed error report file
- **Error N:** Each error with its location in `file:line` format
  - Errors may show a trigger chain using `->` notation: `error_file:line -> trigger_file:line`
  - This indicates the instantiation or call stack that led to the error
- **Source(s) in Command:** Source files (.cpp, .cxx, .cc, .c) being compiled
- **Binary(s) in Command:** Object files (.o, .obj) being generated
- **Errors Found:** Total number of structured errors detected by the parser

**Note:** "Errors Found: 0" means the build failed but no structured compiler errors could be parsed (typically linker errors, warnings-as-errors, or unrecognized diagnostics). The report file still contains the complete output for debugging.

### Understanding Trigger Chains

Template instantiation errors often show a chain of locations:

```
Error 1: /project/lib/vector.h:89 -> /project/src/algorithms.h:234 -> /project/src/main.cpp:56
```

This means:
- **Primary error** occurred at `vector.h:89`
- **Triggered by** code at `algorithms.h:234` 
- **Which was called from** `main.cpp:56`

This helps you quickly identify both the problematic template code and where you're using it.

## Example Use Case

See the complete example below demonstrating how to use this tool with complex template errors and get LLM assistance for fixes.

## Complete Workflow Example

```bash
./quietcc.py g++ -std=c++14 template_error_example.cpp -o template_test
```

**Output:**
```
========================================
Compilation failed (exit code 1).
  Report: /home/dev/EA/error-b2f578d0ab.txt
  Error 1: /home/dev/EA/template_error_example.cpp:45 
  Source(s) in Command: /home/dev/EA/template_error_example.cpp
  Binary(s) in Command: template_test
  Errors Found: 1
========================================
```

See the generated report file for detailed error context, including:
- The exact compilation command
- Filtered compiler diagnostics (errors only, no warnings)
- Source code snippets with line numbers around each error location

The report file path uses a hash of the source files, so multiple compilations of the same source will overwrite the same report file, keeping your build directory clean.

## Configuration

You can customize the tool by editing these variables in `quietcc.py`:

- `SNIP_RADIUS` (default: 25) - Lines of source code shown above and below each error location
- `NUM_ERROR_PRE_LINES` (default: 3) - Lines of compiler output shown before first error
- `NUM_ERROR_POST_LINES` (default: 6) - Lines of compiler output shown after first error
- `ERROR_REPORT_DIR` (default: ".") - Directory for error report files
- `DEFAULT_COMPILER` (default: "cl" on Windows, "g++" on Unix) - Compiler to use in wrapper mode

## Warnings as Errors 

To treat all warnings as errors, enable the following option in your CMake configuration:

```cmake
    set(CMAKE_COMPILE_WARNING_AS_ERROR ON) # globally
    set_target_properties(test_core PROPERTIES COMPILE_WARNING_AS_ERROR ON) # per-target
```

The tool will then capture warnings as errors in the reports.

## License

This tool is provided as-is for developer use.
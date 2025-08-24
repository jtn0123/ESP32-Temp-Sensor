#!/usr/bin/env python3
"""
Batch fix common linting issues in C++ files
"""

import os
import re


def fix_comment_spacing(content):
    """Fix comment spacing issues - ensure at least 2 spaces before //"""
    # Fix single space before // comments
    content = re.sub(r'(\S) //', r'\1  //', content)
    return content

def fix_simple_line_breaks(content):
    """Fix some simple line length issues by breaking at logical points"""
    lines = content.split('\n')
    fixed_lines = []

    for line in lines:
        # Skip comments and preprocessor directives
        if line.strip().startswith('//') or line.strip().startswith('#'):
            fixed_lines.append(line)
            continue

        # If line is too long and contains function calls or declarations
        if len(line) > 80:
            # Try to break at commas in function parameters
            if '(' in line and ')' in line and ',' in line:
                # Find the opening parenthesis and break after each comma
                paren_start = line.find('(')
                if paren_start != -1:
                    prefix = line[:paren_start+1]
                    rest = line[paren_start+1:]
                    # Split parameters and reformat
                    if ',' in rest:
                        parts = rest.split(',')
                        if len(parts) > 1:
                            fixed_lines.append(prefix + parts[0] + ',')
                            for part in parts[1:-1]:
                                fixed_lines.append(' ' * (paren_start + 2) + part.strip() + ',')
                            if parts[-1].strip().endswith(')'):
                                fixed_lines.append(' ' * (paren_start + 2) + parts[-1].strip())
                            continue

        fixed_lines.append(line)

    return '\n'.join(fixed_lines)

def process_file(filepath):
    """Process a single file to fix linting issues"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Apply fixes
        content = fix_comment_spacing(content)
        content = fix_simple_line_breaks(content)

        # Only write if content changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed {filepath}")
            return True
        else:
            return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Main function to process all C++ files"""
    cpp_files = []
    for root, dirs, files in os.walk('/Users/justin/Documents/Github/ESP32-Temp-Sensor/firmware/arduino/src'):
        for file in files:
            if file.endswith('.cpp') or file.endswith('.h'):
                if file != 'icons_generated.h':  # Skip this file for now
                    cpp_files.append(os.path.join(root, file))

    fixed_count = 0
    for filepath in cpp_files:
        if process_file(filepath):
            fixed_count += 1

    print(f"Fixed {fixed_count} files")

if __name__ == '__main__':
    main()

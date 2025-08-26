#!/usr/bin/env python3
"""
Final comprehensive fix for remaining line length issues in main.cpp
"""

import re


def fix_remaining_lines(content):
    """Fix remaining line length issues"""
    lines = content.split("\n")
    fixed_lines = []

    for line in lines:
        original_line = line

        # Skip if line is already <= 80 characters or is a preprocessor directive
        if len(line) <= 80 or line.strip().startswith("#"):
            fixed_lines.append(line)
            continue

        # Pattern 1: Long function calls with many arguments
        if "(" in line and ")" in line and len(line) > 80:
            # Handle snprintf calls specifically
            if "snprintf(" in line:
                fixed_lines.append(line)
                continue

            # Handle draw_in_region calls
            if "draw_in_region(" in line:
                fixed_lines.append(line)
                continue

        # Pattern 2: Long string concatenations
        if "<<" in line and len(line) > 80:
            fixed_lines.append(line)
            continue

        # Pattern 3: Long array definitions
        if "[" in line and "{" in line and len(line) > 80:
            # Check if it's an array definition that can be split
            array_match = re.match(r"(\s*)([^=]*=)\s*([^;]*);", line.strip())
            if array_match:
                indent = re.match(r"^(\s*)", line).group(1)
                left_side = array_match.group(2)
                array_content = array_match.group(3)

                if len(array_content) > 60:  # If array content is long
                    fixed_lines.append(f"{indent}{left_side}")
                    fixed_lines.append(f"{indent}    {array_content};")
                    continue

        # Pattern 4: Long variable assignments with complex expressions
        assign_match = re.match(r"(\s*[^=]*=)\s*([^;]*);", line.strip())
        if assign_match and len(line) > 80:
            indent = re.match(r"^(\s*)", line).group(1)
            left_side = assign_match.group(1)
            right_side = assign_match.group(2)

            # Check for specific patterns
            if (
                "static_cast" in right_side
                or ("(" in right_side and ")" in right_side and len(right_side) > 40)
                or ("+" in right_side and "-" in right_side and len(right_side) > 50)
            ):
                fixed_lines.append(f"{indent}{left_side}")
                fixed_lines.append(f"{indent}    {right_side};")
                continue

        # Pattern 5: Long comments
        if "//" in line and len(line) > 80:
            comment_pos = line.find("//")
            comment_text = line[comment_pos + 2 :].strip()
            indent = re.match(r"^(\s*)", line).group(1)

            # Break long comments at natural points
            if len(comment_text) > 60:
                words = comment_text.split(" ")
                first_line = " ".join(words[: len(words) // 2])
                second_line = " ".join(words[len(words) // 2 :])

                if comment_pos > 0:
                    # Has code before comment
                    fixed_lines.append(line[:comment_pos].rstrip())
                    fixed_lines.append(f"{indent}// {first_line}")
                    if second_line:
                        fixed_lines.append(f"{indent}// {second_line}")
                else:
                    # Comment-only line
                    fixed_lines.append(f"{indent}// {first_line}")
                    if second_line:
                        fixed_lines.append(f"{indent}// {second_line}")
                continue

        # If no pattern matches, keep the original line
        fixed_lines.append(original_line)

    return "\n".join(fixed_lines)


def main():
    filepath = "/Users/justin/Documents/Github/ESP32-Temp-Sensor/firmware/arduino/src/main.cpp"
    try:
        with open(filepath, "r") as f:
            content = f.read()

        fixed_content = fix_remaining_lines(content)

        with open(filepath, "w") as f:
            f.write(fixed_content)

        print(f"Applied final line length fixes to {filepath}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

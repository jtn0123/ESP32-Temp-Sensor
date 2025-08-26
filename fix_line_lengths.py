#!/usr/bin/env python3
"""
Script to fix line length violations in icons_generated.h
Breaks long array initialization lines to stay within 80 characters
"""


def fix_line_lengths(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()

    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Check if line is too long and contains array data
        if len(line) > 80 and "0x" in line and "{" in line:
            # Split the line at appropriate points
            parts = line.split(", ")
            if len(parts) > 10:  # Only split if there are many elements
                # Create new lines with proper indentation
                indent = "    "  # 4 spaces indentation
                new_lines = []
                current_line = indent

                for j, part in enumerate(parts):
                    if part.strip():  # Skip empty parts
                        if len(current_line + part + ", ") > 75:  # Leave some margin
                            if current_line.strip():
                                new_lines.append(current_line.rstrip())
                            current_line = indent + part + ", "
                        else:
                            current_line += part + ", "

                # Add the last part
                if current_line.strip():
                    new_lines.append(current_line.rstrip())

                fixed_lines.extend(new_lines)
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)

        i += 1

    # Write back to file
    with open(file_path, "w") as f:
        f.write("\n".join(fixed_lines) + "\n")


if __name__ == "__main__":
    fix_line_lengths(
        "/Users/justin/Documents/Github/ESP32-Temp-Sensor/firmware/arduino/src/icons_generated.h"
    )

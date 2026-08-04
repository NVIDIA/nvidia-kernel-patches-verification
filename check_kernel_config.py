# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

"""
Kernel config checker - validates kernel configuration against NVIDIA reference specifications.

Usage:
    check-kernel-config -c /boot/config-$(uname -r) grace-baremetal-kernel-config.txt
    check-kernel-config -c /boot/config-$(uname -r) grace-baremetal-kernel-config.txt vera-baremetal-kernel-config.txt vera-baremetal-kernel-config-addendum.txt
"""

import argparse
from dataclasses import dataclass
import operator
from pathlib import Path
import re
import sys

# Comparison operators for safe evaluation
OPERATORS = {
    "==": operator.eq,
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
}


@dataclass(frozen=True)
class KernelConfigSpec:
    """A required kernel configuration value from a reference specification."""

    option: str
    default: str
    comparator: str
    suggestion: str
    table: str
    source: str


def parse_kconfig(filename: str) -> dict:
    """
    Parse kernel config file into a dict.
    """
    config = {}

    with open(filename, "r", encoding="latin-1") as file:
        for line in file:
            line = line.strip()
            match = re.match(r"(CONFIG_\w+)=(.*)", line)
            if match:
                config[match.group(1)] = match.group(2).strip()

    return config


def parse_defconfig(filename: str) -> list[KernelConfigSpec]:
    """
    Parse default config into a dict.

    Tables are parsed dynamically from lines like:
        # Table 7. Bare Metal Configs: Required
    """

    specs = []
    table = ""
    source = Path(filename).name

    with open(filename, "r", encoding="latin-1") as file:
        for line in file:
            line = line.strip()

            # Detect table headers: "# Table <ref>. Table Name"
            table_match = re.match(r"#\s*Table\s+\S+\.\s*(.+)", line)
            if table_match:
                table = table_match.group(1).strip()
                continue

            # Parse CONFIG_*=value with optional comparator in comment
            match = re.search(r"(CONFIG_[^\s]+?)=([^\s]+)(.*)?", line)
            if match:
                comparator = ""
                suggestion = ""
                if match.group(3):
                    sub_match = re.search(r"\[([=<>]+)([^\]]+)\]", match.group(3))
                    if sub_match:
                        comparator = sub_match.group(1)
                        suggestion = sub_match.group(2).strip()
                        comparator = "==" if comparator == "=" else comparator

                specs.append(
                    KernelConfigSpec(
                        option=match.group(1).strip(),
                        default=match.group(2).strip(),
                        comparator=comparator,
                        suggestion=suggestion,
                        table=table,
                        source=source,
                    )
                )

    return specs


def _safe_compare(value: str, comp: str, target: str) -> bool:
    """
    Safely compare two values using the specified operator.
    """
    if comp not in OPERATORS:
        return False
    try:
        return OPERATORS[comp](int(value), int(target))
    except ValueError:
        return OPERATORS[comp](value, target)


def validate_config(
    defconfig: list[KernelConfigSpec], kconfig: dict
) -> dict[str, list[tuple[str, bool, str]]]:
    """
    Validate conformance of kconfig against defconfig.

    Returns:
        Dict mapping table -> list of (option, passed, message) tuples
    """
    tristate = {"y", "n", "m"}
    results: dict[str, list[tuple[str, bool, str]]] = {}

    for spec in defconfig:
        option = spec.option
        value = kconfig.get(option)
        default, comparator = spec.default, spec.comparator
        suggest, table = spec.suggestion, spec.table

        if value is None:
            if default == "n" or suggest == "n":
                results.setdefault(table, []).append((option, True, "not set (expected)"))
            else:
                results.setdefault(table, []).append((option, False, "not found"))
        elif value == default:
            results.setdefault(table, []).append((option, True, f"={value}"))
        elif comparator == "":
            results.setdefault(table, []).append((option, False, f"={value}, expected {default}"))
        elif value in tristate and suggest in tristate:
            if value == suggest:
                results.setdefault(table, []).append((option, True, f"={value}"))
            else:
                results.setdefault(table, []).append((option, False, f"={value}, expected {default} or {suggest}"))
        else:
            # Safe comparison using operator module
            if _safe_compare(value, comparator, suggest):
                results.setdefault(table, []).append((option, True, f"={value}"))
            else:
                msg = f"={value}, expected {default} or {comparator}{suggest}"
                results.setdefault(table, []).append((option, False, msg))

    return results


def print_results(results: dict[str, list[tuple[str, bool, str]]], verbose: bool) -> int:
    """
    Print validation results by table.

    Returns:
        Total number of failed configs.
    """
    total_failed = 0
    print("\nResults:")
    for table, items in results.items():
        passed = sum(1 for _, ok, _ in items if ok)
        failed = len(items) - passed
        total_failed += failed

        print(f"  {table}: {passed}/{len(items)} passed")

        # Show details for failures, or all if verbose
        for option, ok, msg in items:
            if verbose or not ok:
                mark = "PASS" if ok else "FAIL"
                sep = "" if msg.startswith("=") else " "
                print(f"     [{mark}] {option}{sep}{msg}")

    # Summary
    total_configs = sum(len(items) for items in results.values())
    total_passed = total_configs - total_failed
    print(f"\nSummary: {total_passed}/{total_configs} configs passed")

    return total_failed


def main() -> int:
    """
    Main function
    """
    parser = argparse.ArgumentParser(
        description="Check kernel config against NVIDIA reference specification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  check-kernel-config -c /boot/config-$(uname -r) grace-baremetal-kernel-config.txt
  check-kernel-config -c .config grace-baremetal-kernel-config.txt vera-baremetal-kernel-config.txt vera-baremetal-kernel-config-addendum.txt
  check-kernel-config -c /boot/config-6.8.0 grace-baremetal-kernel-config.txt -v
        """
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Path to kernel config file (e.g., /boot/config-$(uname -r) or .config)"
    )
    parser.add_argument(
        "references",
        nargs="+",
        help="Reference specification file(s)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show passed configs in addition to failures"
    )

    args = parser.parse_args()

    # Parse kernel config
    try:
        kconfig = parse_kconfig(args.config)
    except FileNotFoundError:
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        return 1

    # Parse and merge all reference specs
    defconfig = []
    for ref_file in args.references:
        try:
            file_specs = parse_defconfig(ref_file)
            defconfig.extend(file_specs)
            print(f"Loaded {len(file_specs)} specs from {ref_file}")
        except FileNotFoundError:
            print(f"Error: Reference file not found: {ref_file}", file=sys.stderr)
            return 1

    # Validate and print results
    results = validate_config(defconfig, kconfig)
    return print_results(results, args.verbose)


if __name__ == "__main__":
    sys.exit(main())

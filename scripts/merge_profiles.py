import pstats
import glob
import sys
import argparse
import os
from collections import defaultdict


def merge_and_average_profiles(
    profile_dir="/Users/andrew/Documents/dev/awning_wo/profiles",
    output_file="averaged.prof",
    function_filter=None,
    threshold=0.10,
):
    # Find all .prof files (optionally filter by name, e.g., for specific endpoints)
    prof_files = glob.glob(f"{profile_dir}/*.prof")
    if function_filter:
        prof_files = [f for f in prof_files if function_filter in os.path.basename(f)]

    if not prof_files:
        print("No .prof files found in the directory.")
        sys.exit(1)

    num_files = len(prof_files)
    print(f"Merging and averaging {num_files} profiles...")

    # Merge by adding stats from all files
    stats = pstats.Stats(prof_files[0])
    for prof in prof_files[1:]:
        stats.add(prof)

    # Average the stats (divide time-based metrics and call counts by num_files)
    total_cumtime = 0.0  # We'll compute this for relative percentages
    for func, (cc, nc, tt, ct, callers) in list(stats.stats.items()):
        avg_cc = cc / num_files
        avg_nc = nc / num_files
        avg_tt = tt / num_files
        avg_ct = ct / num_files
        avg_callers = {
            k: (v[0] / num_files, v[1] / num_files, v[2] / num_files, v[3] / num_files)
            for k, v in callers.items()
        }
        stats.stats[func] = (avg_cc, avg_nc, avg_tt, avg_ct, avg_callers)
        total_cumtime += avg_ct  # Sum averaged cumtimes for relative calc (approximate total request time)

    # Strip dirs for cleaner output
    stats.strip_dirs()

    # Detailed console report
    print("\nTop 10 Functions by Cumulative Time (cumtime - total incl. sub-calls):")
    stats.sort_stats("cumtime").print_stats(10)

    print("\nTop 10 Functions by Total Time (tottime - excl. sub-calls):")
    stats.sort_stats("tottime").print_stats(10)

    print("\nTop 10 Functions by Call Count (ncalls):")
    stats.sort_stats("ncalls").print_stats(10)

    # Smart Bottleneck Analysis
    print(
        "\nBottleneck Analysis (flagged if >{:.0%} of total cumtime or high per-call time):".format(
            threshold
        )
    )
    module_groups = defaultdict(list)
    for func, (cc, nc, tt, ct, callers) in sorted(
        stats.stats.items(), key=lambda x: x[1][3], reverse=True
    ):  # Sort by avg_cumtime
        filename, lineno, name = func
        module = filename.split(os.sep)[-1] if filename else "unknown"
        relative_cumtime = ct / total_cumtime if total_cumtime > 0 else 0
        per_call_tt = tt / nc if nc > 0 else 0

        flags = []
        if relative_cumtime > threshold:
            flags.append(f"High relative time ({relative_cumtime:.1%} of total)")
        if (
            per_call_tt > 0.01
        ):  # Arbitrary threshold for "slow per call" (adjust based on your app; e.g., >10ms)
            flags.append(f"Slow per call ({per_call_tt:.4f}s)")
        if nc > 100:  # High call count threshold (adjust; e.g., repeated DB calls)
            flags.append(f"High calls ({nc:.0f})")

        if flags:
            module_groups[module].append(
                f"  - {name} ({filename}:{lineno}): {', '.join(flags)} | cumtime={ct:.4f}s, tottime={tt:.4f}s, ncalls={nc:.0f}"
            )

    # Print grouped by module
    for module, items in module_groups.items():
        print(f"\nModule: {module}")
        for item in items[:10]:  # Limit to top 10 per module
            print(item)

    # Save averaged stats for snakeviz
    stats.dump_stats(output_file)
    print(
        f"\nAveraged profile saved to {output_file}. Visualize with: snakeviz {output_file}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge and average .prof files to find bottlenecks."
    )
    parser.add_argument(
        "--profile_dir", default="profiles", help="Directory with .prof files"
    )
    parser.add_argument(
        "--output_file", default="averaged.prof", help="Output .prof file"
    )
    parser.add_argument(
        "--function_filter",
        default=None,
        help="Filter filenames by this string (e.g., endpoint name)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.10,
        help="Relative cumtime threshold for flagging bottlenecks (0-1)",
    )
    args = parser.parse_args()

    merge_and_average_profiles(
        profile_dir=args.profile_dir,
        output_file=args.output_file,
        function_filter=args.function_filter,
        threshold=args.threshold,
    )

import math
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


# Define mass and V^2 values for each configuration
mass_v2_map = {
    1:  ["4.52E-02", "9.07E-03"],
    5:  ["2.15E-05", "1.59E-06", "4.23E-07"],
    10: ["6.30E-07", "2.17E-08"],
    14: ["1.99E-07"],
}

def run_configuration(mass, v2):
    # Convert V^2 to V and format to six decimal places
    v = f"{math.sqrt(float(v2)):.6f}"

    # Input directory
    input_dir_LO = (
        f"/eos/cms/store/group/phys_exotica/HNL/Run3/Results/"
        f"NanoGen/LO/M_lljj-mu_M-{mass}_V-{v}"
        f"_5000Events_Run3Summer24-140X_NanoGEN"
    )

    input_dir_NLO = (
        f"/eos/cms/store/group/phys_exotica/HNL/Run3/Results/"
        f"NanoGen/NLO/M_lljj-mu_M-{mass}_V-{v}"
        f"_5000Events_Run3Summer24-140X_NanoGEN"
    )

    # Output directory for this configuration
    output_dir = Path(
        f"/eos/user/s/snandan/hnl/M-{mass}_V-{v}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    # Command-line arguments for the C++ executable
    cmd = [
        "./compare_LO_vs_NLO",
        input_dir_LO,
        input_dir_NLO,
        str(output_dir),
    ]

    print(f"Starting: mass={mass}, V={v}")

    # Execute the C++ program
    result = subprocess.run(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    )
    # Save stdout and stderr to a log file
    (output_dir / "run.log").write_text(result.stdout)

    if result.returncode == 0:
        print(f"Finished: mass={mass}, V={v}")
    else:
        print(
            f"FAILED: mass={mass}, V={v}. "
            f"Check {output_dir}/run.log"
        )


def main():
    # Flatten the mass-V^2 dictionary into a list of jobs
    jobs = [
        (mass, v2)
        for mass, v2_values in mass_v2_map.items()
        for v2 in v2_values
    ]

    print(f"Total configurations: {len(jobs)}")

    # Run at most four configurations concurrently
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(run_configuration, mass, v2)
            for mass, v2 in jobs
        ]

        # Check each job when it finishes
        for future in as_completed(futures):
            future.result()

    print("All configurations finished.")


if __name__ == "__main__":
    main()

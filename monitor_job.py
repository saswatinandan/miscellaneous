import re
import time
import shlex
import subprocess
import getpass
import argparse
import json
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

CONFIG_PATTERN = (
    "M-HeavyNeutrino_lljj_M*_V*_mu_NLO_Run3Summer24-150X_MiniAODv6"
)

#OUTPUT_BASE = Path("/eos/user/s/snandan/hnl/test")
LOG_DIRECTORY = "LogFiles/Logs"

CHECK_INTERVAL = 300       # 5 minutes
MAX_RETRIES = 3
RESOURCE_FACTOR = 2

username = getpass.getuser()

unlink_logs = {}
# ============================================================
# CONFIGURATION DIRECTORIES
# ============================================================

def get_config_directories():

    return sorted(
        directory
        for directory in Path.cwd().glob(CONFIG_PATTERN)
        if directory.is_dir()
    )


# ============================================================
# FIND CLUSTER IDs AUTOMATICALLY
# ============================================================

def get_cluster_ids(config_name):

    command = (
        f"condor_q -nobatch | grep -F -- {shlex.quote(config_name)}"
    )

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True
    )

    cluster_ids = set()

    for line in result.stdout.splitlines():

        fields = line.split()

        if not fields:
            continue

        job_id = fields[0]  # Example: 21501994.0

        if not re.fullmatch(r"\d+\.\d+", job_id):
            continue

        cluster_id = job_id.split(".")[0]

        cluster_ids.add(int(cluster_id))

    if cluster_ids:
        print(f"{config_name}: Condor clusters = {cluster_ids}")

    return cluster_ids


# ============================================================
# EXPECTED JOBS FROM ORIGINAL JDL FILES
# ============================================================

def get_expected_jobs():

    expected_jobs = {}

    for directory in get_config_directories():

        print('d: ', directory)
        jdl_file = directory / f"{directory.name}.jdl"

        if not jdl_file.exists():
            print(f"WARNING: JDL not found: {jdl_file}")
            continue

        content = jdl_file.read_text(errors="ignore")

        match = re.search(
            r"(?im)^\s*Queue\s+(\d+)\s*$",
            content
        )

        if match:
            expected_jobs[directory.name] = int(match.group(1))
        else:
            print(f"WARNING: Queue statement not found: {jdl_file}")

    return expected_jobs


# ============================================================
# COUNT PRODUCED ROOT FILES
# ============================================================

def get_finished_jobs(OUTPUT_BASE):

    finished_jobs = {}

    for directory in get_config_directories():

        output_dir = OUTPUT_BASE / directory.name

        print('output_dir: ', output_dir)
        if not output_dir.exists():
            finished_jobs[directory.name] = 0
            continue

        finished_jobs[directory.name] = sum(
            1 for file in output_dir.glob("*.root")
            if file.is_file()
        )

    return finished_jobs


# ============================================================
# CONDOR STATUS
# ============================================================

def get_condor_status(cluster_ids):

    status = {
        "idle": 0,
        "running": 0,
        "held": 0,
        "total": 0
    }

    for cluster_id in cluster_ids:

        result = subprocess.run(
            [
                "condor_q",
                "-constraint",
                f"ClusterId == {cluster_id}",
                "-af",
                "JobStatus"
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(
                f"ERROR checking cluster {cluster_id}: "
                f"{result.stderr}"
            )
            continue

        for line in result.stdout.splitlines():

            line = line.strip()

            if not line.isdigit():
                continue

            job_status = int(line)
            status["total"] += 1

            if job_status == 1:
                status["idle"] += 1

            elif job_status == 2:
                status["running"] += 1

            elif job_status == 5:
                status["held"] += 1

    return status


def rm_logfiles(config_dir):
    print(config_dir)
    print([f for f in unlink_logs[config_dir]])
    for f in unlink_logs[config_dir]:
        f.unlink()

# ============================================================
# FAILURE DETECTION FROM LOG FILES
# ============================================================

def get_old_configuration(job_id, condition):

    result = subprocess.run(
         ["timeout", "10s", "condor_history", job_id, "-limit", "1", "-af", condition],
         capture_output=True,
         text=True
    )
    
    return result.stdout.strip()

def get_failed_jobs(seen_logs):

    failed_jobs = {}

    memory_pattern = re.compile(
        r"out of memory|memory exceeded|oom-kill|"
        r"memory limit|exceeded memory",
        re.IGNORECASE
    )

    time_pattern = re.compile(
        r"job exceeded.*(time|runtime)|wall.?time.*exceeded|"
        r"maximum runtime|runtime limit|timed out|"
        r"time limit exceeded",
        re.IGNORECASE
    )

    other_pattern = re.compile(
        r"OnExitRemove expression.*"
        r"NumJobCompletions\s*>\s*JobMaxRetries\s*\|\|\s*"
        r"ExitCode\s*=\?=\s*JobSuccessExitCode.*"
        r"evaluated to FALSE",
        re.IGNORECASE
    )
    
    for directory in get_config_directories():

        log_dir = directory / LOG_DIRECTORY

        memory_failed, old_memory = 0,[]
        time_failed, old_time = 0,[]
        other_failed = 0

        if log_dir.exists():

            for log_file in log_dir.iterdir():

                if log_file is not None:
                    signature = (
                        str(log_file),
                        log_file.stat().st_mtime_ns,
                        log_file.stat().st_size
                    )

                    if signature not in seen_logs:

                        clusterid, process = log_file.name.split('_')[0], log_file.name.split('_')[1].split('.')[0]
                        job_id = f"{clusterid}.{process}"
                        
                        content = log_file.read_text(errors="ignore")

                        is_memory_failure = bool(memory_pattern.search(content))
                        is_time_failure = bool(time_pattern.search(content))
                        is_other_failure = bool(other_pattern.search(content))

                        if is_memory_failure:
                            memory_failed += 1
                            if not directory in unlink_logs.keys():
                                unlink_logs[directory] = []
                            unlink_logs[directory].append(log_file)
                            print('memory: ', directory, '\t', log_file)
                            old_memory.append(get_old_configuration(job_id, 'MemoryUsage'))

                        elif is_time_failure:
                            time_failed += 1
                            if not directory in unlink_logs.keys():
                                unlink_logs[directory] = []
                            print('time: ', directory, '\t', log_file)
                            unlink_logs[directory].append(log_file)
                            old_time.append(get_old_configuration(job_id, 'MaxRunTime'))

                        elif is_other_failure:
                            other_failed += 1
                            if not directory in unlink_logs.keys():
                                unlink_logs[directory] = []
                            print('other: ', log_file)
                            unlink_logs[directory].append(log_file)

                        seen_logs.add(signature)
        if directory in unlink_logs.keys(): print('1st: ', [f for f in unlink_logs[directory]])
        failed_jobs[directory.name] = {
            "memory": (memory_failed, max(old_memory, default=0)),
            "time": (time_failed, max(old_time, default=0)),
            "other": other_failed
        }
    return failed_jobs


# ============================================================
# CREATE AND SUBMIT RETRY JDL
# ============================================================

def resubmit_failed_jobs(
    config_dir,
    failure_type,
    failed_jobs,
    old_val=""
):

    if failed_jobs <= 0:
        return None

    original_jdl = config_dir / f"{config_dir.name}.jdl"

    if not original_jdl.exists():
        raise FileNotFoundError(f"No JDL file found in {config_dir}")

    print(f"Using JDL file: {original_jdl.name}")

    content = original_jdl.read_text()


    if failure_type == "memory":
        resource_pattern = (
            r"(?im)^(\s*request_memory\s*=\s*)(\d+)(\s*)$"
        )
        retry_type = "memory"

    elif failure_type == "time":
        resource_pattern = (
            r"(?im)^(\s*\+MaxRuntime\s*=\s*)(\d+)(\s*)$"
        )
        retry_type = "time"

    elif failure_type == "other":
        resource_pattern = None
        retry_type = "other"

    else:
        raise ValueError(f"Unknown failure type: {failure_type}")

    new_resource = int(old_val or 0) * RESOURCE_FACTOR
    print('new_resource: ', new_resource,'\t', old_val)
    retry_number = 1
    if failure_type != 'other':
         retry_jdls = list(config_dir.glob(
            f"{config_dir.name}_{failure_type}_retry*{new_resource}*.jdl"
         ))
         if retry_jdls:
            retry_number = max(
             [int(m.group(1)) for f in retry_jdls
             if (m := re.search(r"_retry_(\d+_)?(\d+)$", f.stem))],
              default=0
            ) + 1
    else:
        retry_jdls = list(config_dir.glob(
            f"{config_dir.name}_{failure_type}_retry_*.jdl"
         ))
        if retry_jdls:
            retry_number = max(
                [int(m.group(1)) for f in retry_jdls
                if (m := re.search(r"_retry_(\d+)$", f.stem))],
                default=0
             ) + 1

    suffix = f"_{retry_type}_retry_{new_resource}_{retry_number}" if old_val else f"_{retry_type}_retry_{retry_number}"

    if resource_pattern is not None:
         content = re.sub(
            resource_pattern,
            lambda match: (
            match.group(1)
            + str(new_resource)
            + match.group(3)
        ),
        content,
        count=1
    )

    # Replace Queue with the number of failed jobs.
    queue_pattern = r"(?im)^\s*Queue\s+\d+\s*$"

    if not re.search(queue_pattern, content):
        print(f"ERROR: Queue statement not found in {original_jdl}")
        return None

    content = re.sub(
        queue_pattern,
        f"Queue {failed_jobs}",
        content,
        count=1
    )

    base_name = re.sub(
        r"_(?:time|memory|other)_retry_(?:\d+)$",
        "",
        original_jdl.stem
    )

    new_jdl = original_jdl.with_name(
        base_name + suffix + ".jdl"
    )

    new_jdl.write_text(content)

    print("\nSubmitting retry JDL:", new_jdl)
    print("Failure type:", failure_type)
    print("Failed jobs:", failed_jobs)
    print("New resource:", new_resource)

    result = subprocess.run(
        ["condor_submit", str(new_jdl)],
        cwd=config_dir,
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.returncode != 0:
        print("Submission failed:")
        print(result.stderr)
        sys.exit()
        return None

    cluster_match = re.search(
        r"submitted to cluster\s+(\d+)",
        result.stdout,
        re.IGNORECASE
    )

    if cluster_match:

        cluster_id = int(cluster_match.group(1))

        print("New retry cluster ID:", cluster_id)

        return cluster_id

    print("WARNING: Could not identify cluster ID.")

    return None


# ============================================================
# WAIT INTERVAL
# ============================================================

def wait_for_next_check():

    #print("\nWaiting 5 minutes before next monitoring check...")
    print(f"\nWaiting 5 minutes from {datetime.now().strftime('%H:%M:%S')} before next monitoring check...")

    time.sleep(CHECK_INTERVAL)


# ============================================================
# MAIN MONITORING FUNCTION
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Monitor output directories for completed ROOT files"
    )

    parser.add_argument(
        "-o", "--output-dir",
        required=True,
        help="Base output directory to search"
    )

    args = parser.parse_args()

    input_file = Path.cwd() / "failed_jobs.json"

    if input_file.exists():
        with open(input_file, "r") as f:
            failed_job = json.load(f)

        print(json.dumps(failed_job, indent=4))
    
    OUTPUT_BASE = Path(args.output_dir)
    print('OUTPUT_BASE: ', OUTPUT_BASE)

    expected_jobs = get_expected_jobs()

    total_jobs = sum(expected_jobs.values())

    if total_jobs == 0:
        print("No expected jobs found. Check your JDL files.")
        return

    # Automatically discovered original and retry cluster IDs.
    cluster_ids = set()

    # Track already inspected log files.
    seen_logs = set()

    print("\n========== PRODUCTION MONITOR ==========")
    print("Total expected jobs:", total_jobs)

    retry_count = {}
    for config_name in expected_jobs.keys():
        retry_count[config_name] = {
            'time_retry': 0,
            'memory_retry': 0,
            'other_retry': 0
        }

    while True:

        print("\n\n========================================")
        print("          MONITORING CHECK")
        print("========================================")

        # ----------------------------------------------------
        # 1. Count finished ROOT files.
        # ----------------------------------------------------

        print("\nROOT FILE STATUS")

        finished_jobs = get_finished_jobs(OUTPUT_BASE)

        total_finished = total_missing = 0

        for config_name, expected in expected_jobs.items():

            finished = finished_jobs.get(config_name, 0)

            total_finished += finished

            missing = max(expected - finished, 0)

            total_missing += missing

            print(
                f"{config_name}: "
                f"Expected={expected}, "
                f"Finished={finished}, "
                f"Missing={missing}"
            )

        print("\nTotal expected:", total_jobs)
        print("Total finished:", total_finished)
        print("Total missing:", total_missing)

        # ----------------------------------------------------
        # 2. Stop if all ROOT files exist.
        # ----------------------------------------------------

        if total_missing == 0:

            print("\nSUCCESS: All ROOT files have been produced!")
            break

        # ----------------------------------------------------
        # 3. Discover cluster IDs for every configuration.
        # ----------------------------------------------------

        print("\nDISCOVERING CONDOR CLUSTER IDs")

        for config_name in expected_jobs:

            current_cluster_ids = get_cluster_ids(config_name)

            cluster_ids.update(current_cluster_ids)

        print("\nAll known cluster IDs:", cluster_ids)

        # ----------------------------------------------------
        # 4. Check Condor status.
        # ----------------------------------------------------

        condor_status = get_condor_status(cluster_ids)

        idle = condor_status["idle"]
        running = condor_status["running"]
        held = condor_status["held"]
        queued = condor_status["total"]

        print("\nCONDOR STATUS")

        print("Idle jobs:    ", idle)
        print("Running jobs: ", running)
        print("Held jobs:    ", held)

        # ----------------------------------------------------
        # 5. Compare missing files with active/held jobs.
        # ----------------------------------------------------

        unaccounted = max(total_missing - queued, 0)

        print("Unaccounted missing jobs:", unaccounted)

        if unaccounted == 0:

            print(
                "\nMissing files are accounted for by jobs "
                "still present in Condor."
            )

            print("No resubmission will be performed.")

            wait_for_next_check()

            continue

        # ----------------------------------------------------
        # 6. Check retry limit.
        # ----------------------------------------------------

        print("\nINSPECTING FAILURE LOGS")

        failed_jobs = get_failed_jobs(seen_logs)

        new_cluster_ids = []

        # ----------------------------------------------------
        # 8. Resubmit eligible failed jobs.
        # ----------------------------------------------------

        for config_name, failures in failed_jobs.items():

            expected = expected_jobs.get(config_name, 0)

            finished = finished_jobs.get(config_name, 0)

            missing = expected - finished

            assert( missing >= 0 )

            if missing == 0:
                continue

            # Find cluster IDs for this failed configuration.
            current_cluster_ids = get_cluster_ids(config_name)

            cluster_ids.update(current_cluster_ids)

            print(
                f"\nCurrently active clusters for {config_name}: "
                f"{current_cluster_ids}"
            )

            memory_failed, old_memory = failures["memory"]

            time_failed, old_time = failures["time"]

            print('time_failed: ', time_failed)
            other_failed = failures["other"]

            print(f"\nConfiguration: {config_name}")
            print("Missing files:", missing)
            print("Memory failures:", memory_failed)
            print("Time failures:", time_failed)
            print("Others failures:", other_failed)

            config_dir = Path.cwd() / config_name

            # Limit retries to the number of missing outputs.
            memory_to_retry = memory_failed #min(memory_failed, missing)

            time_to_retry = time_failed #min(
            #    time_failed,
            #    max(missing - memory_to_retry, 0)
            #)

            other_to_retry = other_failed #min(
            #    other_failed,
            #    max(missing - (memory_to_retry+time_to_retry), 0)
            #)

            # Memory failure retry.
            if (memory_to_retry > 0): # and (retry_count[config_name]['memory_retry'] <= MAX_RETRIES):

                cluster_id = resubmit_failed_jobs(
                    config_dir,
                    "memory",
                    memory_to_retry,
                    old_memory
                )

                if cluster_id is not None:
                    new_cluster_ids.append(cluster_id)
                    retry_count[config_name]['memory_retry'] += memory_to_retry

            # Time failure retry.
            if (time_to_retry > 0): # and (retry_count[config_name]['time_retry'] <= MAX_RETRIES):

                cluster_id = resubmit_failed_jobs(
                    config_dir,
                    "time",
                    time_to_retry,
                    old_time
                )

                if cluster_id is not None:
                    new_cluster_ids.append(cluster_id)
                    retry_count[config_name]['time_retry'] += time_to_retry

            '''if other_failed : # and (retry_count[config_name]['other_retry'] <= MAX_RETRIES):

                cluster_id = resubmit_failed_jobs(
                    config_dir,
                    "other",
                    other_to_retry
                )

                if cluster_id is not None:
                    new_cluster_ids.append(cluster_id)
                    retry_count[config_name]['other_retry'] += other_to_retry '''
            
            rm_logfiles(config_dir)
        # ----------------------------------------------------
        # 9. Update cluster IDs and retry counter.
        # ----------------------------------------------------

        if new_cluster_ids:

            cluster_ids.update(new_cluster_ids)

            print(
                f"\nRetry found {retry_count} with {MAX_RETRIES} submitted."
            )

        else:
            running_jobs = [
               job for job in json.loads(
                subprocess.run(
                ["condor_q", "-json", username],
                capture_output=True,
                text=True,
                 check=True
                ).stdout
            )
            if job.get("JobStatus") == 2
            ]
            if len(running_jobs):
                print('-------------------')
                print('jobs are submitted already')
                print('-------------------')
            else:
                print(
                    "No retry submitted because max limit"
                    "No job running."
                    "Exiting"
                )
                

        # ----------------------------------------------------
        # 10. Wait before next monitoring check.
        # ----------------------------------------------------

        wait_for_next_check()

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    final_finished = get_finished_jobs(OUTPUT_BASE)

    final_total = sum(final_finished.values())

    print("\n\n========== FINAL SUMMARY ==========")

    print("Expected ROOT files:", total_jobs)
    print("Produced ROOT files:", final_total)
    print("Missing ROOT files:", max(total_jobs - final_total, 0))
    print("Retry rounds used:", retry_count)


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":

    main()

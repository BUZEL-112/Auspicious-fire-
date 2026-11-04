"""Bootstrap and test Fashion Vision Pipeline on Google Colab instance."""

import os
import subprocess
import sys


def run(cmd: str, cwd: str = "/content") -> None:
    print(f"\n>>> Running: {cmd} (in {cwd})", flush=True)
    p = subprocess.Popen(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if p.stdout is not None:
        for line in iter(p.stdout.readline, ""):
            sys.stdout.write(line)
            sys.stdout.flush()
    p.wait()
    if p.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {p.returncode}: {cmd}")


def main() -> None:
    repo = "https://github.com/BUZEL-112/Auspicious-fire-.git"
    branch = os.environ.get("COLAB_BRANCH", "feat/phase2-wardrobe-recommendation")
    target = "/content/Auspicious-fire-"

    # 1. Clone or pull repository
    if not os.path.exists(target):
        run(f"git clone -b {branch} {repo} {target}")
    else:
        run(f"git fetch origin && git checkout {branch} && git pull origin {branch}", cwd=target)

    # 2. Setup environment
    run("bash scripts/colab_setup.sh", cwd=target)

    # 3. Start services
    run("bash scripts/start_services.sh", cwd=target)

    # 4. Check initial service status
    run("bash scripts/status_services.sh", cwd=target)

    # 5. Execute Stage 1 and Stage 2 pipeline verification
    run("python scripts/test_pipeline_e2e.py", cwd=target)

    # 6. Execute Dummy Wardrobe Ingestion and Outfit Recommendations verification
    run("python scripts/test_wardrobe_recommendations_e2e.py", cwd=target)

    # 7. Final service inspection
    run("bash scripts/status_services.sh", cwd=target)

    print("\n>>> All verification steps completed successfully on Google Colab.", flush=True)


if __name__ == "__main__":
    main()

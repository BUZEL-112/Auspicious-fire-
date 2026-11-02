"""Interactive Terminal Agent for Fashion Vision Pipeline.

Allows the user to speak directly to the agent in the terminal to inspect,
start, test, and control the pipeline.
"""

import os
import subprocess
import sys
import httpx


class FashionTerminalAgent:
    def __init__(self):
        self.api_url = "http://localhost:8000"
        self.prompt_symbol = "FashionAgent> "

    def print_welcome(self):
        print("=================================================================")
        print("Fashion Vision Pipeline: Personal Terminal Agent")
        print("Type 'help' to see available commands or type your message.")
        print("Type 'exit' or 'quit' to terminate.")
        print("=================================================================")

    def run(self):
        self.print_welcome()
        while True:
            try:
                user_input = input(self.prompt_symbol).strip()
            except (KeyboardInterrupt, EOFError):
                print("\nSession ended.")
                break

            if not user_input:
                continue

            cmd_lower = user_input.lower()
            if cmd_lower in ("exit", "quit", "q"):
                print("Goodbye.")
                break
            elif cmd_lower in ("help", "?"):
                self.handle_help()
            elif cmd_lower == "status":
                self.handle_status()
            elif cmd_lower == "start":
                self.handle_start()
            elif cmd_lower == "stop":
                self.handle_stop()
            elif cmd_lower == "test":
                self.handle_test()
            elif cmd_lower == "logs":
                self.handle_logs()
            else:
                self.handle_general_query(user_input)

    def handle_help(self):
        print("\nAvailable Commands:")
        print("  status  - Check health of PostgreSQL, MinIO, Kafka, and API")
        print("  start   - Launch all background services without Docker")
        print("  stop    - Terminate all running services")
        print("  test    - Run end-to-end pipeline verification test")
        print("  logs    - View recent service logs")
        print("  exit    - Exit the agent terminal\n")

    def handle_status(self):
        print("\nChecking pipeline service status...")
        script_path = "scripts/status_services.sh"
        if os.path.exists(script_path):
            subprocess.run(["bash", script_path])
        else:
            try:
                resp = httpx.get(f"{self.api_url}/healthz", timeout=3.0)
                print(f"API Healthz: {resp.status_code} - {resp.json()}")
            except Exception as e:
                print(f"API not reachable: {e}")

    def handle_start(self):
        print("\nStarting services with scripts/start_services.sh...")
        subprocess.run(["bash", "scripts/start_services.sh"])

    def handle_stop(self):
        print("\nStopping services with scripts/stop_services.sh...")
        subprocess.run(["bash", "scripts/stop_services.sh"])

    def handle_test(self):
        print("\nExecuting end-to-end pipeline verification test...")
        subprocess.run([sys.executable, "scripts/test_pipeline_e2e.py"])

    def handle_logs(self):
        log_files = ["logs/api.log", "logs/worker.log", "logs/kafka.log", "logs/minio.log"]
        for log in log_files:
            if os.path.exists(log):
                print(f"\n--- {log} (last 5 lines) ---")
                with open(log, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-5:]
                    print("".join(lines))

    def handle_general_query(self, query: str):
        # Fallback assistant response
        q_lower = query.lower()
        if "stage 1" in q_lower or "stage1" in q_lower:
            print("\nStage 1 performs single-garment tagging using FashionCLIP embeddings and Grouped Softmax.")
            print("Use command 'test' to run Stage 1 verification.")
        elif "stage 2" in q_lower or "stage2" in q_lower:
            print("\nStage 2 performs SegFormer outfit segmentation, isolates pieces, and extracts multi-garment attributes.")
            print("Use command 'test' to run Stage 2 verification.")
        elif "colab" in q_lower or "t4" in q_lower:
            print("\nTo run in Google Colab T4:")
            print("1. Use google-colab-cli: colab new --gpu T4 -s fashion-test")
            print("2. Pull origin branch feat/colab-local-runner")
            print("3. Run: bash scripts/colab_setup.sh && bash scripts/start_services.sh")
        else:
            print(f"\nReceived instruction: '{query}'")
            print("You can run 'test', 'status', 'start', 'stop', or 'logs'.")


if __name__ == "__main__":
    agent = FashionTerminalAgent()
    agent.run()

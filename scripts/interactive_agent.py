"""Interactive Terminal Agent for Fashion Vision Pipeline and Wardrobe Recommendations.

Allows the user to speak directly to the agent in the terminal to inspect,
start, test, and control the pipeline and recommendation engine.
Works with zero third-party dependencies using standard Python libraries.
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


def _http_get(url: str, timeout: float = 5.0):
    req = urllib.request.Request(url, headers={"User-Agent": "FashionAgent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _http_post(url: str, payload: dict, timeout: float = 10.0):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "FashionAgent/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


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

            parts = user_input.split()
            cmd = parts[0].lower()
            args = parts[1:]

            if cmd in ("exit", "quit", "q"):
                print("Goodbye.")
                break
            elif cmd in ("help", "?"):
                self.handle_help()
            elif cmd == "status":
                self.handle_status()
            elif cmd == "start":
                self.handle_start()
            elif cmd == "stop":
                self.handle_stop()
            elif cmd == "test":
                self.handle_test()
            elif cmd in ("test-wardrobe", "test_wardrobe"):
                self.handle_test_wardrobe()
            elif cmd == "wardrobe":
                user_id = args[0] if args else "user_001"
                self.handle_wardrobe(user_id)
            elif cmd == "recommend":
                user_id = args[0] if args else "user_001"
                self.handle_recommend(user_id)
            elif cmd == "logs":
                self.handle_logs()
            else:
                self.handle_general_query(user_input)

    def handle_help(self):
        print("\nAvailable Commands:")
        print("  status              - Check health of PostgreSQL, MinIO, Kafka, and API")
        print("  start               - Launch all background services without Docker")
        print("  stop                - Terminate all running background services")
        print("  test                - Run Stage 1 and Stage 2 pipeline verification test")
        print("  test-wardrobe       - Run Phase 2 wardrobe and recommendation test suite")
        print("  wardrobe [user_id]  - View all stored garments for a user (default: user_001)")
        print("  recommend [user_id] - Request outfit recommendations interactively")
        print("  logs                - View recent service log outputs")
        print("  exit                - Exit the agent terminal\n")

    def handle_status(self):
        print("\nChecking pipeline service status...")
        script_path = "scripts/status_services.sh"
        if os.path.exists(script_path):
            subprocess.run(["bash", script_path])
        else:
            try:
                status, data = _http_get(f"{self.api_url}/healthz", timeout=3.0)
                print(f"API Healthz: {status} - {data}")
            except Exception as e:
                print(f"API not reachable: {e}")

    def handle_start(self):
        print("\nStarting services with scripts/start_services.sh...")
        subprocess.run(["bash", "scripts/start_services.sh"])

    def handle_stop(self):
        print("\nStopping services with scripts/stop_services.sh...")
        subprocess.run(["bash", "scripts/stop_services.sh"])

    def handle_test(self):
        print("\nExecuting Phase 1 pipeline verification test...")
        subprocess.run([sys.executable, "scripts/test_pipeline_e2e.py"])

    def handle_test_wardrobe(self):
        print("\nExecuting Phase 2 wardrobe and recommendation test suite...")
        subprocess.run([sys.executable, "scripts/test_wardrobe_recommendations_e2e.py"])

    def handle_wardrobe(self, user_id: str):
        print(f"\nFetching wardrobe for user '{user_id}'...")
        try:
            status, data = _http_get(f"{self.api_url}/api/v1/users/{user_id}/wardrobe", timeout=5.0)
            if status != 200:
                print(f"Failed to fetch wardrobe: HTTP {status}")
                return
            total = data.get("total_items", 0)
            items = data.get("items", [])
            print(f"User {user_id} has {total} registered garments:")
            for itm in items:
                print(
                    f" - [{itm.get('item_id')}] Slot: {itm.get('slot')}, "
                    f"Category: {itm.get('category')}, Color: {itm.get('color')}, "
                    f"Fabric: {itm.get('fabric')}, Status: {itm.get('status')}"
                )
        except Exception as e:
            print(f"Error connecting to API gateway: {e}")

    def handle_recommend(self, user_id: str):
        print(f"\nRequesting outfit recommendations for user '{user_id}'...")
        print("Select occasion: [casual_daily, work_office, date_night, formal_event, party_social]")
        occasion = input("Occasion (default: casual_daily): ").strip() or "casual_daily"
        print("Select weather: [hot, warm, mild, cold, freezing, rainy]")
        weather = input("Weather (default: mild): ").strip() or "mild"
        print("Select formality: [ultra_casual, smart_casual, business_casual, semi_formal]")
        formality = input("Formality (optional): ").strip() or None

        payload = {"occasion": occasion, "weather": weather}
        if formality:
            payload["formality"] = formality

        try:
            status, result = _http_post(
                f"{self.api_url}/api/v1/users/{user_id}/recommendations?top_k=3",
                payload=payload,
                timeout=10.0,
            )
            if status != 200:
                print(f"Recommendation request failed: HTTP {status}")
                return
            outfits = result.get("outfits", [])
            print(f"\nReceived {len(outfits)} recommended outfits:")
            for idx, outfit in enumerate(outfits, 1):
                score = outfit.get("total_score")
                score_str = f"{score:.2f}" if score is not None else "N/A"
                print(f"\n--- Outfit {idx} (Score: {score_str} / 100) ---")
                print(f" Rationale: {outfit.get('rationale')}")
                for slot, g in outfit.get("items", {}).items():
                    print(f"  * {slot.upper()}: {g.get('category')} ({g.get('color')}, {g.get('fabric')})")
        except Exception as e:
            print(f"Error querying recommendation service: {e}")

    def handle_logs(self):
        log_files = ["logs/api.log", "logs/worker.log", "logs/kafka.log", "logs/minio.log"]
        for log in log_files:
            if os.path.exists(log):
                print(f"\n--- {log} (last 5 lines) ---")
                with open(log, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-5:]
                    print("".join(lines))

    def handle_general_query(self, query: str):
        q_lower = query.lower()
        if "stage 1" in q_lower or "stage1" in q_lower:
            print("\nStage 1 performs single-garment tagging using FashionCLIP embeddings and Grouped Softmax.")
            print("Use command 'test' to run Stage 1 verification.")
        elif "stage 2" in q_lower or "stage2" in q_lower:
            print("\nStage 2 performs SegFormer outfit segmentation, isolates pieces, and extracts multi-garment attributes.")
            print("Use command 'test' to run Stage 2 verification.")
        elif "wardrobe" in q_lower or "recommend" in q_lower:
            print("\nPhase 2 provides Wardrobe Ingestion and Heuristic Outfit Recommendations.")
            print("Use command 'wardrobe <user_id>' to inspect garments or 'recommend <user_id>' to generate outfits.")
        elif "colab" in q_lower:
            print("\nTo operate on Google Colab:")
            print("1. Run CPU test: bash scripts/colab_cpu_runner.sh fashion-cpu")
            print("2. Run GPU test: bash scripts/colab_t4_runner.sh fashion-gpu")
            print("3. Terminate instance: colab stop -s fashion-cpu")
        else:
            print(f"\nReceived instruction: '{query}'")
            print("You can run 'test', 'test-wardrobe', 'wardrobe', 'recommend', 'status', 'start', 'stop', or 'logs'.")


if __name__ == "__main__":
    agent = FashionTerminalAgent()
    agent.run()

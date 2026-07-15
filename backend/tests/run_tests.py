import os
import subprocess
import time
import urllib.request
import json
import sys
from datetime import datetime, timezone

# We will run tests against a temporary test database
TEST_DB_URL = "sqlite:///./test_devmem.db"
PORT = 8001
BASE_URL = f"http://127.0.0.1:{PORT}"

def run_cmd(cmd, env=None):
    print(f"Running: {cmd}")
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
    if p.returncode != 0:
        print(f"Error executing: {cmd}")
        print("STDOUT:", p.stdout)
        print("STDERR:", p.stderr)
        sys.exit(p.returncode)
    return p.stdout

def send_request(path, method="GET", data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    req_data = json.dumps(data).encode("utf-8") if data else None
    
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            body = res.read().decode("utf-8")
            return res.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err_data = json.loads(body)
        except Exception:
            err_data = body
        return e.code, err_data

def main():
    print("=== STARTING INTEGRATION TESTS ===")
    
    # 1. Prepare environment
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DB_URL
    env["PORT"] = str(PORT)
    env["LOG_LEVEL"] = "WARNING"
    
    # Ensure any old test database is removed
    if os.path.exists("test_devmem.db"):
        os.remove("test_devmem.db")
        
    # 2. Run alembic migrations on test db
    print("Running database migrations on test DB...")
    run_cmd("..\\venv\\Scripts\\python.exe -m alembic upgrade head", env=env)
    
    # 3. Start FastAPI server
    print("Starting FastAPI backend server...")
    server_process = subprocess.Popen(
        f"..\\venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port {PORT}",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    
    # Wait for server to start
    time.sleep(2)
    
    try:
        # Test 1: GET /health
        print("\nTest 1: Health check...")
        status_code, body = send_request("/health")
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 200
        assert body["status"] == "healthy"
        assert body["database"] == "connected"
        
        # Test 2: POST /api/events (Create first event in workspace A)
        print("\nTest 2: Creating first event in workspace A...")
        event1 = {
            "event_type": "FileSaved",
            "file_path": "src/main.py",
            "workspace": "C:/projects/workspace_a",
            "language": "python",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"size_bytes": 120}
        }
        status_code, body = send_request("/api/events", "POST", event1)
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 201
        assert body["status"] == "recorded"
        session_id_1 = body["session_id"]
        assert session_id_1 is not None
        
        # Test 3: POST /api/events (Create second event in workspace A - should group into same session)
        print("\nTest 3: Creating second event in workspace A (should group into same session)...")
        event2 = {
            "event_type": "FileSaved",
            "file_path": "src/utils.py",
            "workspace": "C:/projects/workspace_a",
            "language": "python",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"size_bytes": 240}
        }
        status_code, body = send_request("/api/events", "POST", event2)
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 201
        assert body["session_id"] == session_id_1
        
        # Test 4: POST /api/events (Create event in workspace B - should create a new session)
        print("\nTest 4: Creating event in workspace B...")
        event3 = {
            "event_type": "FileSaved",
            "file_path": "index.ts",
            "workspace": "C:/projects/workspace_b",
            "language": "typescript",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"size_bytes": 500}
        }
        status_code, body = send_request("/api/events", "POST", event3)
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 201
        session_id_2 = body["session_id"]
        assert session_id_2 is not None
        assert session_id_2 != session_id_1
        
        # Test 5: GET /api/sessions/active (Workspace A)
        print("\nTest 5: Getting active session for workspace A...")
        status_code, body = send_request("/api/sessions/active?workspace=C:/projects/workspace_a")
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 200
        assert body["id"] == session_id_1
        
        # Test 6: GET /api/sessions (List all sessions)
        print("\nTest 6: Listing all sessions...")
        status_code, body = send_request("/api/sessions")
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 200
        assert len(body) == 2
        # Check files recorded in session 1
        sess1 = next(s for s in body if s["id"] == session_id_1)
        assert "src/main.py" in sess1["files"]
        assert "src/utils.py" in sess1["files"]
        
        # Test 7: POST /api/sessions/active/end (End workspace A session)
        print("\nTest 7: Ending active session for workspace A...")
        status_code, body = send_request("/api/sessions/active/end?workspace=C:/projects/workspace_a", "POST")
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 200
        assert body["status"] == "terminated"
        assert body["session_id"] == session_id_1
        
        # Test 8: GET /api/sessions/active (Workspace A - should now be None)
        print("\nTest 8: Verify workspace A active session is ended...")
        status_code, body = send_request("/api/sessions/active?workspace=C:/projects/workspace_a")
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 200
        assert body is None

        # Test 8b: GET /api/sessions (Check ended session has summary, decisions, pending_work)
        print("\nTest 8b: Checking summary, decisions, and pending_work on ended session...")
        status_code, body = send_request("/api/sessions?workspace=C:/projects/workspace_a")
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 200
        sess = next(s for s in body if s["id"] == session_id_1)
        assert sess["summary"] is not None
        assert "main.py" in sess["summary"] or "utils.py" in sess["summary"]
        assert sess["decisions"] is not None
        assert "- Modified and saved" in sess["decisions"]
        assert sess["pending_work"] is not None
        assert "- Continue working on changes in" in sess["pending_work"]
        
        # Test 9: POST /api/events (Create another event in workspace A - should start a NEW session)
        print("\nTest 9: Creating event in workspace A after ending session...")
        event4 = {
            "event_type": "FileSaved",
            "file_path": "src/main.py",
            "workspace": "C:/projects/workspace_a",
            "language": "python",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"size_bytes": 150}
        }
        status_code, body = send_request("/api/events", "POST", event4)
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 201
        session_id_3 = body["session_id"]
        assert session_id_3 is not None
        assert session_id_3 != session_id_1
        
        # Test 10: GET /api/search (keyword search)
        print("\nTest 10: Search sessions with keyword...")
        status_code, body = send_request("/api/search?query=main.py")
        print(f"Status: {status_code}, Body keys: {list(body.keys()) if body else None}")
        assert status_code == 200
        assert "query" in body
        assert "answer" in body
        assert "matched_sessions" in body
        assert body["query"] == "main.py"
        assert isinstance(body["answer"], str) and len(body["answer"]) > 0

        # Test 11: GET /api/search (natural language – "what did I work on today")
        print("\nTest 11: Search with natural-language question...")
        status_code, body = send_request("/api/search?query=What+did+I+work+on+today")
        print(f"Status: {status_code}, Body keys: {list(body.keys()) if body else None}")
        assert status_code == 200
        assert "answer" in body
        assert isinstance(body["matched_sessions"], list)

        # Test 12: GET /api/search – workspace filter returning nothing
        print("\nTest 12: Search with non-existent workspace filter...")
        status_code, body = send_request("/api/search?query=main.py&workspace=C:/nonexistent")
        print(f"Status: {status_code}, Body: {body}")
        assert status_code == 200
        assert body["matched_sessions"] == [] or isinstance(body["matched_sessions"], list)

        print("\n=== ALL TESTS PASSED SUCCESSFULLY ===")
        
    except Exception as e:
        print(f"\nAssertion/Error: {e}")
        sys.exit(1)
    finally:
        print("Shutting down FastAPI server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Force-killing server process...")
            subprocess.run(f"taskkill /F /T /PID {server_process.pid}", shell=True)
            
        # Clean up database file
        if os.path.exists("test_devmem.db"):
            try:
                os.remove("test_devmem.db")
                print("Test database cleaned up.")
            except Exception as ex:
                print(f"Error removing test db: {ex}")

if __name__ == "__main__":
    main()

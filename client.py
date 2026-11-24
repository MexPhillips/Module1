"""Interactive TCP client for the newline-delimited JSON quiz protocol."""

import argparse
import json
import socket

from server import DEFAULT_HOST, DEFAULT_PORT, MAX_MESSAGE_BYTES


class RemoteError(Exception):
    """An error response returned by the quiz server."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code


class QuizClient:
    """Send and receive one JSON message per line over a TCP connection."""

    def __init__(self, host, port):
        self.socket = socket.create_connection((host, port))
        self.reader = self.socket.makefile("rb")

    def request(self, request):
        payload = json.dumps(request, separators=(",", ":")).encode("utf-8") + b"\n"
        self.socket.sendall(payload)
        line = self.reader.readline(MAX_MESSAGE_BYTES + 1)
        if not line:
            raise ConnectionError("The server closed the connection.")
        if len(line) > MAX_MESSAGE_BYTES or not line.endswith(b"\n"):
            raise ValueError("The server returned an invalid or oversized message.")
        try:
            response = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("The server returned malformed JSON.") from exc
        if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
            raise ValueError("The server returned an invalid response object.")
        if not response["ok"]:
            error = response.get("error", {})
            raise RemoteError(
                error.get("code", "server_error"),
                error.get("message", "The request could not be completed."),
            )
        return response

    def close(self):
        self.reader.close()
        self.socket.close()


def print_menu():
    print("\n1) Get a question")
    print("2) Submit an answer")
    print("3) Get score")
    print("4) Quit")


def run_client(host, port):
    try:
        client = QuizClient(host, port)
    except OSError as exc:
        print(f"Could not connect to {host}:{port}: {exc}")
        return 1

    current_question_id = None
    print(f"Connected to quiz server at {host}:{port}.")
    try:
        while True:
            print_menu()
            choice = input("Choose an action: ").strip()
            if choice == "1":
                try:
                    response = client.request({"type": "GET_QUESTION"})
                except RemoteError as exc:
                    print(f"Request failed: {exc}")
                    continue
                current_question_id = response["question_id"]
                print(f"\n{response['question']}")
                for letter, text in response["choices"].items():
                    print(f"  {letter}) {text}")
            elif choice == "2":
                if current_question_id is None:
                    print("Get a question before submitting an answer.")
                    continue
                answer = input("Your answer (A-D): ").strip().upper()
                try:
                    response = client.request(
                        {
                            "type": "SUBMIT_ANSWER",
                            "question_id": current_question_id,
                            "answer": answer,
                        }
                    )
                except RemoteError as exc:
                    print(f"Request failed: {exc}")
                    continue
                print(response["message"])
                print(f"Score: {response['score']}")
                current_question_id = None
            elif choice == "3":
                try:
                    response = client.request({"type": "GET_SCORE"})
                except RemoteError as exc:
                    print(f"Request failed: {exc}")
                    continue
                print(f"Current score: {response['score']}")
            elif choice == "4":
                print("Goodbye.")
                return 0
            else:
                print("Choose 1, 2, 3, or 4.")
    except (ConnectionError, OSError, ValueError) as exc:
        print(f"Connection error: {exc}")
        return 1
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description="Connect to the TCP quiz server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Quiz server hostname.")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Quiz server TCP port."
    )
    args = parser.parse_args()
    return run_client(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())

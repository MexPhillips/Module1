"""TCP server for the newline-delimited JSON quiz protocol."""

import argparse
import json
import logging
import socketserver


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
MAX_MESSAGE_BYTES = 64 * 1024

QUESTIONS = (
    {
        "id": "Q1",
        "question": "Which protocol provides a reliable, ordered byte stream?",
        "choices": {
            "A": "UDP",
            "B": "TCP",
            "C": "ICMP",
            "D": "ARP",
        },
        "answer": "B",
    },
    {
        "id": "Q2",
        "question": "Which Python module provides low-level networking interfaces?",
        "choices": {
            "A": "socket",
            "B": "json",
            "C": "pathlib",
            "D": "argparse",
        },
        "answer": "A",
    },
    {
        "id": "Q3",
        "question": "What character terminates each message in this application's protocol?",
        "choices": {
            "A": "A comma",
            "B": "A tab",
            "C": "A newline",
            "D": "A semicolon",
        },
        "answer": "C",
    },
)


def error_response(code, message):
    """Create the common error envelope used by all protocol failures."""
    return {"ok": False, "error": {"code": code, "message": message}}


def process_request(request, session):
    """Validate and process one decoded request for a connected client."""
    if not isinstance(request, dict):
        return error_response("invalid_request", "A request must be a JSON object.")

    request_type = request.get("type")
    if not isinstance(request_type, str):
        return error_response(
            "invalid_request", "The request must include a string 'type' field."
        )

    if request_type == "GET_QUESTION":
        if set(request) != {"type"}:
            return error_response(
                "invalid_fields", "GET_QUESTION accepts only the 'type' field."
            )
        question = QUESTIONS[session["next_question_index"]]
        session["next_question_index"] = (
            session["next_question_index"] + 1
        ) % len(QUESTIONS)
        session["current_question"] = question
        session["answered"] = False
        return {
            "ok": True,
            "type": "QUESTION",
            "question_id": question["id"],
            "question": question["question"],
            "choices": question["choices"],
        }

    if request_type == "SUBMIT_ANSWER":
        if set(request) != {"type", "question_id", "answer"}:
            return error_response(
                "invalid_fields",
                "SUBMIT_ANSWER requires 'type', 'question_id', and 'answer'.",
            )
        answer = request["answer"]
        if not isinstance(answer, str) or answer.upper() not in {"A", "B", "C", "D"}:
            return error_response(
                "invalid_answer", "Answer must be one of A, B, C, or D."
            )
        question_id = request["question_id"]
        if not isinstance(question_id, str):
            return error_response(
                "invalid_question", "'question_id' must be a string."
            )
        question = session["current_question"]
        if question is None or question_id != question["id"]:
            return error_response(
                "invalid_question",
                "Request the current question before submitting its answer.",
            )
        if session["answered"]:
            return error_response(
                "already_answered",
                "This question has already been answered. Request another question.",
            )

        correct = answer.upper() == question["answer"]
        session["answered"] = True
        if correct:
            session["score"] += 1
        return {
            "ok": True,
            "type": "ANSWER_RESULT",
            "correct": correct,
            "message": "Correct!" if correct else f"Incorrect. The correct answer is {question['answer']}.",
            "score": session["score"],
        }

    if request_type == "GET_SCORE":
        if set(request) != {"type"}:
            return error_response(
                "invalid_fields", "GET_SCORE accepts only the 'type' field."
            )
        return {"ok": True, "type": "SCORE", "score": session["score"]}

    return error_response(
        "unknown_request", f"Unknown request type: {request_type}."
    )


class QuizRequestHandler(socketserver.StreamRequestHandler):
    """Handle multiple newline-delimited requests on one TCP connection."""

    def handle(self):
        peer = f"{self.client_address[0]}:{self.client_address[1]}"
        logging.info("Client connected: %s", peer)
        session = {
            "score": 0,
            "current_question": None,
            "answered": False,
            "next_question_index": 0,
        }

        try:
            while True:
                line = self.rfile.readline(MAX_MESSAGE_BYTES + 1)
                if not line:
                    break
                if len(line) > MAX_MESSAGE_BYTES:
                    self._send(error_response(
                        "message_too_large",
                        f"Messages may not exceed {MAX_MESSAGE_BYTES} bytes.",
                    ))
                    if not line.endswith(b"\n"):
                        break
                    continue
                if not line.endswith(b"\n"):
                    self._send(error_response(
                        "invalid_framing",
                        "Each request must end with a newline.",
                    ))
                    break

                try:
                    request = json.loads(line.decode("utf-8").strip())
                except (UnicodeDecodeError, json.JSONDecodeError):
                    response = error_response(
                        "malformed_json", "Request must contain valid UTF-8 JSON."
                    )
                else:
                    response = process_request(request, session)
                self._send(response)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            logging.info("Client disconnected unexpectedly: %s", peer)
        finally:
            logging.info("Client disconnected: %s", peer)

    def _send(self, response):
        payload = json.dumps(response, separators=(",", ":")).encode("utf-8") + b"\n"
        self.request.sendall(payload)


class QuizTCPServer(socketserver.ThreadingTCPServer):
    """Threaded TCP server that supports simultaneous quiz clients."""

    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description="Run the TCP quiz server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Interface to bind to.")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="TCP port to listen on."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    try:
        with QuizTCPServer((args.host, args.port), QuizRequestHandler) as server:
            logging.info("Quiz server listening on %s:%s", args.host, args.port)
            server.serve_forever()
    except OSError as exc:
        parser.exit(1, f"Could not start server on {args.host}:{args.port}: {exc}\n")
    except KeyboardInterrupt:
        logging.info("Server stopped.")


if __name__ == "__main__":
    main()

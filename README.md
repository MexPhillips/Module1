# Overview

This project is a small TCP client-server quiz application. It demonstrates how two independent Python programs can exchange structured requests, validate input, and keep track of a user's score. The goal is to practice reliable message framing, request handling, and clear separation between a client interface and server logic.

Start the server in one terminal and the client in another. The client automatically presents five multiple-choice questions, advances after each answer, and displays the final score only after the fifth answer. The server accepts multiple connections; each connection has its own quiz progress and score. Reconnecting starts a new session.

**Software Demo Video:** [https://youtu.be/BeAsIgZbim4)

# Network Communication

The application uses a client/server architecture over TCP. The server binds to `127.0.0.1` by default and listens on port `5000`. Both host and port can be changed with command-line options.

Requests and responses are UTF-8 JSON objects, each terminated by a newline. TCP is a byte stream, so the newline provides the message boundary. The client sends each complete request with `sendall`; the server reads one line at a time and sends one newline-terminated response.

Supported request examples:

```json
{"type":"GET_QUESTION"}
{"type":"SUBMIT_ANSWER","question_id":"Q1","answer":"B"}
{"type":"GET_SCORE"}
```

Successful responses include `"ok": true`; errors include `"ok": false` and an `error` object with a stable code and readable message. A submitted answer must be A, B, C, or D (case-insensitive) and refer to the current question. Each question can be answered once.

# Development Environment

The project was developed with Python 3 and Visual Studio Code. It uses only Python's standard library: `socket` and `socketserver` for TCP communication, `json` for message encoding, and `argparse` for command-line options. No packages need to be installed.

## Installation

1. Install Python 3.8 or newer and ensure `python` is available in your terminal.
2. Open a terminal in the project folder. There are no external dependencies and no `pip install` step.

## Run the server

In the first terminal:

```text
python server.py
```

The server reports the address it is listening on. To select a different interface or port:

```text
python server.py --host 127.0.0.1 --port 5001
```

Press `Ctrl+C` to stop the server.

## Run the client

In a second terminal:

```text
python client.py
```

The client starts the five-question quiz automatically. Submit an answer for each question to advance to the next one. The final score appears only after the fifth answer. To connect to a server on another host or port:

```text
python client.py --host 127.0.0.1 --port 5001
```

Quit and relaunch the client to reconnect. The server remains running and accepts the new connection; each new connection starts with a score of zero.

## Example interaction

```text
Connected to quiz server at 127.0.0.1:5000.

Question 1 of 5
Which protocol provides a reliable, ordered byte stream?
  A) UDP
  B) TCP
  C) ICMP
  D) ARP

Your answer (A-D): B
Correct!

Question 2 of 5
...

Final score: 5 out of 5
Quiz complete!
```

An incorrect answer is reported explicitly and does not increase the score:

```text
Your answer (A-D): A
Incorrect. The correct answer is B.
```

## Tests

Run the integration tests from the project folder:

```text
python -m unittest discover -s tests -v
```

The tests start a local TCP server on an available port and exercise question retrieval, correct and incorrect answers, score tracking, malformed and invalid requests, repeated submissions, and disconnect/reconnect behavior.

# Useful Websites

* [Python socket documentation](https://docs.python.org/3/library/socket.html)
* [Python socketserver documentation](https://docs.python.org/3/library/socketserver.html)
* [Python JSON documentation](https://docs.python.org/3/library/json.html)
* [BYU-Idaho CSE 310 course resources](https://byui-cse.github.io/cse310-course/)

# Future Work

* Add a larger question bank and randomized question selection.
* Persist scores across client sessions.
* Add automated client-side reconnection after an unexpected network failure.

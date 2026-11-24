import json
import socket
import threading
import unittest

from server import QuizRequestHandler, QuizTCPServer


class QuizServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Start an ephemeral local TCP server before the integration tests run."""
        cls.server = QuizTCPServer(("127.0.0.1", 0), QuizRequestHandler)
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.server_thread.start()
        cls.address = cls.server.server_address

    @classmethod
    def tearDownClass(cls):
        """Stop and close the test server after all integration tests finish."""
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)

    def connect(self):
        """Create a connected socket and binary line reader for one test client."""
        connection = socket.create_connection(self.address, timeout=2)
        connection.settimeout(2)
        return connection, connection.makefile("rb")

    @staticmethod
    def send(reader_socket, reader, request):
        """Send one JSON request and decode exactly one newline-delimited response."""
        reader_socket.sendall(
            json.dumps(request, separators=(",", ":")).encode("utf-8") + b"\n"
        )
        return json.loads(reader.readline().decode("utf-8"))

    def test_question_correct_answer_score_and_multiple_requests(self):
        """Verify questions, a correct answer, score updates, and multiple requests."""
        connection, reader = self.connect()
        with connection, reader:
            question = self.send(connection, reader, {"type": "GET_QUESTION"})
            self.assertTrue(question["ok"])
            self.assertEqual(question["question_id"], "Q1")
            self.assertEqual(set(question["choices"]), {"A", "B", "C", "D"})

            result = self.send(
                connection,
                reader,
                {
                    "type": "SUBMIT_ANSWER",
                    "question_id": "Q1",
                    "answer": "b",
                },
            )
            self.assertTrue(result["correct"])
            self.assertNotIn("score", result)
            score = self.send(connection, reader, {"type": "GET_SCORE"})
            self.assertEqual(score["score"], 1)

    def test_quiz_contains_five_questions_and_blocks_extra_questions(self):
        """Verify the server serves exactly five questions in a quiz session."""
        connection, reader = self.connect()
        with connection, reader:
            answers = ("B", "A", "C", "B", "B")
            for index in range(1, 6):
                question = self.send(connection, reader, {"type": "GET_QUESTION"})
                self.assertEqual(question["question_number"], index)
                self.assertEqual(question["question_count"], 5)

                result = self.send(
                    connection,
                    reader,
                    {
                        "type": "SUBMIT_ANSWER",
                        "question_id": question["question_id"],
                        "answer": answers[index - 1],
                    },
                )
                self.assertTrue(result["correct"])
                self.assertEqual(
                    result["quiz_complete"],
                    index == 5,
                )

            score = self.send(connection, reader, {"type": "GET_SCORE"})
            self.assertEqual(score["score"], 5)

            extra_question = self.send(
                connection, reader, {"type": "GET_QUESTION"}
            )
            self.assertEqual(extra_question["error"]["code"], "quiz_complete")

    def test_incorrect_answer_does_not_increase_score_and_cannot_repeat(self):
        """Verify incorrect answers leave the score unchanged and cannot repeat."""
        connection, reader = self.connect()
        with connection, reader:
            self.send(connection, reader, {"type": "GET_QUESTION"})
            result = self.send(
                connection,
                reader,
                {
                    "type": "SUBMIT_ANSWER",
                    "question_id": "Q1",
                    "answer": "A",
                },
            )
            self.assertFalse(result["correct"])
            self.assertIn("Incorrect", result["message"])
            self.assertNotIn("score", result)
            repeated = self.send(
                connection,
                reader,
                {
                    "type": "SUBMIT_ANSWER",
                    "question_id": "Q1",
                    "answer": "B",
                },
            )
            self.assertEqual(repeated["error"]["code"], "already_answered")

    def test_invalid_requests_and_malformed_json_are_safe(self):
        """Verify malformed and invalid requests return errors without breaking the connection."""
        connection, reader = self.connect()
        with connection, reader:
            connection.sendall(b"{not-json}\n")
            malformed = json.loads(reader.readline().decode("utf-8"))
            self.assertEqual(malformed["error"]["code"], "malformed_json")

            unknown = self.send(connection, reader, {"type": "NOT_A_REQUEST"})
            self.assertEqual(unknown["error"]["code"], "unknown_request")
            invalid = self.send(
                connection,
                reader,
                {
                    "type": "SUBMIT_ANSWER",
                    "question_id": "Q1",
                    "answer": "Z",
                },
            )
            self.assertEqual(invalid["error"]["code"], "invalid_answer")
            missing = self.send(
                connection, reader, {"type": "SUBMIT_ANSWER", "answer": "A"}
            )
            self.assertEqual(missing["error"]["code"], "invalid_fields")
            still_usable = self.send(connection, reader, {"type": "GET_SCORE"})
            self.assertEqual(still_usable["score"], 0)

    def test_disconnect_and_reconnect_starts_a_new_session(self):
        """Verify closing a connection and reconnecting creates a fresh quiz session."""
        first, first_reader = self.connect()
        first.close()
        first_reader.close()

        second, second_reader = self.connect()
        with second, second_reader:
            score = self.send(second, second_reader, {"type": "GET_SCORE"})
            self.assertEqual(score["score"], 0)
            question = self.send(second, second_reader, {"type": "GET_QUESTION"})
            self.assertEqual(question["question_id"], "Q1")


if __name__ == "__main__":
    # Run this module directly to execute the integration test suite.
    unittest.main()

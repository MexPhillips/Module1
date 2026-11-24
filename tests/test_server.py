import json
import socket
import threading
import unittest

from server import QuizRequestHandler, QuizTCPServer


class QuizServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = QuizTCPServer(("127.0.0.1", 0), QuizRequestHandler)
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.server_thread.start()
        cls.address = cls.server.server_address

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)

    def connect(self):
        connection = socket.create_connection(self.address, timeout=2)
        connection.settimeout(2)
        return connection, connection.makefile("rb")

    @staticmethod
    def send(reader_socket, reader, request):
        reader_socket.sendall(
            json.dumps(request, separators=(",", ":")).encode("utf-8") + b"\n"
        )
        return json.loads(reader.readline().decode("utf-8"))

    def test_question_correct_answer_score_and_multiple_requests(self):
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
            self.assertEqual(result["score"], 1)
            score = self.send(connection, reader, {"type": "GET_SCORE"})
            self.assertEqual(score["score"], 1)

    def test_incorrect_answer_does_not_increase_score_and_cannot_repeat(self):
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
            self.assertEqual(result["score"], 0)
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
    unittest.main()

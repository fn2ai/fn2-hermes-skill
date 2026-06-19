"""
Unit tests for the bundled `fn2` CLI.

These run fully offline — every network call is mocked — so they need no API key
and are safe to run in CI. They load the CLI by path so the same test file works
whether the script lives at skills/fn2/scripts/fn2 (Hermes) or scripts/fn2
(OpenClaw).
"""

import argparse
import importlib.util
import io
import json
import socket
import unittest
import urllib.error
from contextlib import redirect_stdout
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
_CANDIDATES = [
    ROOT / "skills" / "fn2" / "scripts" / "fn2",  # Hermes layout
    ROOT / "scripts" / "fn2",                       # OpenClaw layout
]


def _load_cli():
    path = next((p for p in _CANDIDATES if p.exists()), None)
    if path is None:
        raise FileNotFoundError(f"Could not find the fn2 CLI in any of: {_CANDIDATES}")
    loader = SourceFileLoader("fn2cli", str(path))
    spec = importlib.util.spec_from_loader("fn2cli", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


fn2 = _load_cli()


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._body = json.dumps(payload).encode("utf-8") if payload is not None else b""

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeSSEResponse:
    """A urlopen-like response that is a context manager and iterates byte lines."""

    def __init__(self, lines):
        self._lines = list(lines)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._lines)


def make_http_error(code, payload):
    body = json.dumps(payload).encode("utf-8")
    return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(body))


class CleanAnswerTests(unittest.TestCase):
    def test_strips_citation_markers(self):
        out = fn2._clean_answer("NVDA rose 5%{{cite:abc-123}} on strong demand.", raw=False)
        self.assertEqual(out, "NVDA rose 5% on strong demand.")

    def test_raw_keeps_markers(self):
        text = "NVDA rose 5%{{cite:abc-123}}."
        self.assertEqual(fn2._clean_answer(text, raw=True), text)

    def test_tidies_space_before_punctuation(self):
        out = fn2._clean_answer("Up today {{cite:x}}, then flat.", raw=False)
        self.assertEqual(out, "Up today, then flat.")

    def test_empty(self):
        self.assertEqual(fn2._clean_answer("", raw=False), "")


class ScheduleTests(unittest.TestCase):
    def _args(self, **kw):
        defaults = dict(cron=None, every=None, at=None, timezone=None, ends=None)
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def test_cron(self):
        s = fn2._build_schedule(self._args(cron="0 9 * * 1"))
        self.assertEqual(s["frequency"], "custom")
        self.assertEqual(s["cron"], "0 9 * * 1")
        self.assertEqual(s["timezone"], "UTC")

    def test_every(self):
        s = fn2._build_schedule(self._args(every="weekdays", timezone="America/Denver"))
        self.assertEqual(s["frequency"], "weekdays")
        self.assertEqual(s["timezone"], "America/Denver")
        self.assertNotIn("cron", s)

    def test_at(self):
        s = fn2._build_schedule(self._args(at="2026-07-01T09:00:00"))
        self.assertEqual(s["run_at"], "2026-07-01T09:00:00")

    def test_none(self):
        self.assertIsNone(fn2._build_schedule(self._args()))


class HttpMessageTests(unittest.TestCase):
    def test_401(self):
        msg = fn2._http_message(401, {"error": "bad key"})
        self.assertIn("401", msg)
        self.assertIn("bad key", msg)

    def test_403_mentions_scope(self):
        self.assertIn("scope", fn2._http_message(403, {"error": "Missing scope: agents"}).lower())

    def test_429_mentions_quota(self):
        self.assertIn("Quota", fn2._http_message(429, {"error": "limit"}))


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict("os.environ", {"FN2_API_KEY": "fn2_test_key", "FN2_API_BASE": "https://x/api/v1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_happy_path_returns_json(self):
        with mock.patch.object(fn2.urllib.request, "urlopen", return_value=FakeResponse(200, {"ok": True})):
            status, data = fn2.request("GET", "/models")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"ok": True})

    def test_sends_bearer_and_body(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["auth"] = req.get_header("Authorization")
            captured["method"] = req.get_method()
            captured["body"] = req.data
            return FakeResponse(201, {"id": "a1"})

        with mock.patch.object(fn2.urllib.request, "urlopen", side_effect=fake_urlopen):
            fn2.request("POST", "/agents", body={"prompt": "hi"})
        self.assertEqual(captured["auth"], "Bearer fn2_test_key")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "https://x/api/v1/agents")
        self.assertEqual(json.loads(captured["body"]), {"prompt": "hi"})

    def test_query_params_drop_none(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            return FakeResponse(200, {"agents": []})

        with mock.patch.object(fn2.urllib.request, "urlopen", side_effect=fake_urlopen):
            fn2.request("GET", "/agents", params={"status": None, "limit": 10})
        self.assertIn("limit=10", captured["url"])
        self.assertNotIn("status", captured["url"])

    def test_http_error_raises_clean(self):
        with mock.patch.object(fn2.urllib.request, "urlopen", side_effect=make_http_error(429, {"error": "over limit"})):
            with self.assertRaises(fn2.Fn2Error) as ctx:
                fn2.request("GET", "/models")
        self.assertIn("Quota", str(ctx.exception))

    def test_http_error_non_dict_body_does_not_crash(self):
        # A 4xx/5xx whose JSON body is an array/string must not raise AttributeError.
        with mock.patch.object(fn2.urllib.request, "urlopen", side_effect=make_http_error(429, ["over limit"])):
            with self.assertRaises(fn2.Fn2Error) as ctx:
                fn2.request("GET", "/models")
        self.assertIn("over limit", str(ctx.exception))

    def test_timeout_raises_clean(self):
        # socket.timeout is a distinct class on Python < 3.10; must still map cleanly.
        with mock.patch.object(fn2.urllib.request, "urlopen", side_effect=socket.timeout("slow")):
            with self.assertRaises(fn2.Fn2Error) as ctx:
                fn2.request("GET", "/models")
        self.assertIn("timed out", str(ctx.exception).lower())

    def test_missing_key_raises(self):
        with mock.patch.dict("os.environ", {"FN2_API_KEY": ""}, clear=False):
            with self.assertRaises(fn2.Fn2Error):
                fn2.request("GET", "/models")


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict("os.environ", {"FN2_API_KEY": "fn2_test_key", "FN2_API_BASE": "https://x/api/v1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    @staticmethod
    def _sse(*objs):
        # urlopen response is iterable over byte lines; mimic the SSE wire format.
        lines = []
        for o in objs:
            lines.append(("data: " + json.dumps(o)).encode("utf-8"))
            lines.append(b"")
        return FakeSSEResponse(lines)

    def test_iter_sse_skips_non_data_lines(self):
        resp = FakeSSEResponse([b": comment", b"data: {\"a\":1}", b"", b"garbage", b"data: notjson"])
        events = list(fn2._iter_sse(resp))
        self.assertEqual(events, [{"a": 1}])

    def test_iter_sse_multiline_event(self):
        # one event whose JSON spans two data: lines, dispatched on the blank line
        resp = FakeSSEResponse([b'data: {"type":"done",', b'data: "status":"success"}', b""])
        events = list(fn2._iter_sse(resp))
        self.assertEqual(events, [{"type": "done", "status": "success"}])

    def test_stream_chat_timeout_raises_clean(self):
        with mock.patch.object(fn2.urllib.request, "urlopen", side_effect=socket.timeout()):
            with self.assertRaises(fn2.Fn2Error) as ctx:
                fn2.stream_chat("q")
        self.assertIn("timed out", str(ctx.exception).lower())

    def test_stream_chat_accumulates_text(self):
        resp = self._sse(
            {"type": "progress", "message": "working"},
            {"type": "streaming_content", "content_type": "text", "content": "NV"},
            {"type": "streaming_content", "content_type": "text", "content": "DA."},
            {"type": "streaming_content", "content_type": "chart", "content": "IGNORED"},
            {"type": "done", "model": "m1", "status": "success", "usage": {"total_tokens": 5},
             "history": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "NVDA."}]},
        )
        with mock.patch.object(fn2.urllib.request, "urlopen", return_value=resp):
            text, meta = fn2.stream_chat("q", model="m1")
        self.assertEqual(text, "NVDA.")
        self.assertEqual(meta["model"], "m1")
        self.assertEqual(meta["usage"], {"total_tokens": 5})

    def test_stream_chat_prefers_clean_final_over_narration(self):
        resp = self._sse(
            {"type": "streaming_content", "content_type": "text", "content": "Let me pull the data. "},
            {"type": "streaming_content", "content_type": "text", "content": "Digging deeper. "},
            {"type": "done", "status": "success", "history": [
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": None},
                {"role": "assistant", "content": "The clean final answer."}]},
        )
        with mock.patch.object(fn2.urllib.request, "urlopen", return_value=resp):
            text, _ = fn2.stream_chat("q")
        self.assertEqual(text, "The clean final answer.")

    def test_final_from_history_skips_null_turns(self):
        hist = [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": None},
            {"role": "tool", "content": "tool output"},
            {"role": "assistant", "content": "answer"},
        ]
        self.assertEqual(fn2._final_from_history(hist), "answer")

    def test_stream_chat_falls_back_to_history(self):
        resp = self._sse(
            {"type": "done", "model": "m1", "status": "success",
             "history": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "From history"}]},
        )
        with mock.patch.object(fn2.urllib.request, "urlopen", return_value=resp):
            text, _ = fn2.stream_chat("q")
        self.assertEqual(text, "From history")

    def test_stream_chat_raises_on_error_event(self):
        resp = self._sse({"type": "error", "message": "boom"})
        with mock.patch.object(fn2.urllib.request, "urlopen", return_value=resp):
            with self.assertRaises(fn2.Fn2Error) as ctx:
                fn2.stream_chat("q")
        self.assertIn("boom", str(ctx.exception))


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict("os.environ", {"FN2_API_KEY": "fn2_test_key"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_research_prints_clean_answer(self):
        args = argparse.Namespace(question="q", model=None, raw=False, json=False)
        with mock.patch.object(fn2, "stream_chat", return_value=("Answer{{cite:z}} here.", {})):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = fn2.cmd_research(args)
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue().strip(), "Answer here.")

    def test_research_json_shape(self):
        args = argparse.Namespace(question="q", model=None, raw=False, json=True)
        meta = {"model": "m1", "usage": {"total_tokens": 9}, "status": "success"}
        with mock.patch.object(fn2, "stream_chat", return_value=("Answer{{cite:z}}", meta)):
            buf = io.StringIO()
            with redirect_stdout(buf):
                fn2.cmd_research(args)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["response"], "Answer{{cite:z}}")  # raw text in --json
        self.assertEqual(out["model"], "m1")
        self.assertEqual(out["usage"], {"total_tokens": 9})
        self.assertEqual(out["status"], "success")

    def test_agents_create_builds_schedule_body(self):
        args = argparse.Namespace(
            prompt="brief", name="My Agent", model=None, label=None,
            cron="0 9 * * 1", every=None, at=None, timezone="UTC", ends=None, json=False,
        )
        captured = {}

        def fake_request(method, path, body=None, **kw):
            captured["method"], captured["path"], captured["body"] = method, path, body
            return (201, {"id": "a1", "name": "My Agent", "schedule": {"cron": "0 9 * * 1"}})

        with mock.patch.object(fn2, "request", side_effect=fake_request):
            buf = io.StringIO()
            with redirect_stdout(buf):
                fn2.cmd_agents_create(args)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["path"], "/agents")
        self.assertEqual(captured["body"]["prompt"], "brief")
        self.assertEqual(captured["body"]["schedule"]["frequency"], "custom")
        self.assertEqual(captured["body"]["schedule"]["cron"], "0 9 * * 1")

    def test_agents_update_requires_a_field(self):
        args = argparse.Namespace(id="a1", name=None, prompt=None, model=None, label=None, json=False)
        with self.assertRaises(fn2.Fn2Error):
            fn2.cmd_agents_update(args)

    def test_research_exit_code(self):
        ok = argparse.Namespace(question="q", model=None, raw=False, json=False)
        with mock.patch.object(fn2, "stream_chat", return_value=("answer", {"status": "success"})):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(fn2.cmd_research(ok), 0)
        with mock.patch.object(fn2, "stream_chat", return_value=("", {"status": "error"})):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(fn2.cmd_research(ok), 2)

    def test_models_renders_with_null_model_id(self):
        args = argparse.Namespace(json=False)
        rows = [{"model_id": None, "display_name": None, "model_class": "fast",
                 "is_default": False, "locked": False}]
        with mock.patch.object(fn2, "request", return_value=(200, rows)):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(fn2.cmd_models(args), 0)  # must not raise on None model_id

    def test_usage_renders_with_string_tokens(self):
        args = argparse.Namespace(json=False)
        payload = {"plan": "free", "tokens": {"used": "100", "limit": "1000", "remaining": "900"}}
        with mock.patch.object(fn2, "request", return_value=(200, payload)):
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(fn2.cmd_usage(args), 0)  # string token counts must not crash
        self.assertIn("100 used", buf.getvalue())

    def test_agents_list_and_run_render(self):
        agents_payload = (200, {"agents": [{"id": "a1", "name": "X", "status": "active",
                                            "schedule": {"frequency": "daily"}, "run_count": 2}], "total": 1})
        with mock.patch.object(fn2, "request", return_value=agents_payload):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(fn2.cmd_agents_list(argparse.Namespace(status=None, limit=50, json=False)), 0)
        run_payload = (202, {"run_id": "r1", "status": "pending"})
        with mock.patch.object(fn2, "request", return_value=run_payload):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(fn2.cmd_agents_run(argparse.Namespace(id="a1", json=False)), 0)

    def test_parser_research(self):
        ns = fn2.build_parser().parse_args(["research", "hello"])
        self.assertEqual(ns.question, "hello")
        self.assertIs(ns.func, fn2.cmd_research)

    def test_parser_requires_subcommand(self):
        with self.assertRaises(SystemExit):
            fn2.build_parser().parse_args([])


class OnboardingTests(unittest.TestCase):
    def test_signup_url_carries_source(self):
        self.assertIn("fn2.ai", fn2.SIGNUP_URL)
        self.assertIn("ref=" + fn2.FN2_SOURCE, fn2.SIGNUP_URL)
        self.assertIn(fn2.FN2_SOURCE, fn2.USER_AGENT)

    def test_missing_key_message_points_to_signup(self):
        with mock.patch.dict("os.environ", {"FN2_API_KEY": ""}, clear=False):
            with self.assertRaises(fn2.Fn2Error) as ctx:
                fn2._key()
        self.assertIn(fn2.SIGNUP_URL, str(ctx.exception))

    def test_401_message_points_to_signup(self):
        self.assertIn(fn2.SIGNUP_URL, fn2._http_message(401, {"error": "bad"}))


if __name__ == "__main__":
    unittest.main()

"""La console deve gestire il gateway senza riaccendere un modello locale."""

import importlib.util
import os
import types
import unittest
from pathlib import Path
from unittest import mock


def load_control(environment):
    spec = importlib.util.spec_from_file_location("gateway_control", Path(__file__).with_name("control.py"))
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(os.environ, environment, clear=True):
        spec.loader.exec_module(module)
    return module


class ControlGatewayTests(unittest.TestCase):
    def test_start_targets_gateway_and_never_local_model(self):
        control = load_control({"LOCAL_LLM_SERVICE": "omniroute.service"})
        handler = types.SimpleNamespace(headers={"X-Control-Token": control.TOKEN},
                                        path="/api/system/on", json=mock.Mock())
        with mock.patch.object(control, "systemctl", return_value=types.SimpleNamespace(returncode=0)) as command:
            control.Handler.do_POST(handler)
        self.assertIn("omniroute.service", command.call_args.args)
        self.assertNotIn("local-ai-llama.service", command.call_args.args)

    def test_remote_model_info_does_not_probe_llama(self):
        control = load_control({"LOCAL_LLM_SERVICE": "omniroute.service", "LOCAL_LLM_MODEL": "free/model"})
        with mock.patch.object(control, "fetch_json") as fetch, mock.patch.object(control, "run") as run:
            info = control.model_info({})
        self.assertEqual(info["alias"], "free/model")
        self.assertIsNone(info["context"])
        fetch.assert_not_called()
        run.assert_not_called()

    def test_default_service_remains_local(self):
        control = load_control({})
        self.assertEqual(control.UNITS["llm"], "local-ai-llama.service")

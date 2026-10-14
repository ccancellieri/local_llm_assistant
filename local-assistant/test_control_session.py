"""Regressioni del rinnovo della sessione dopo un riavvio della console."""

import json
import shutil
import subprocess
import types
import unittest
from unittest import mock

from test_control_gateway import load_control


class ControlSessionTests(unittest.TestCase):
    def test_stale_token_is_rejected_before_any_action(self):
        control = load_control({})
        handler = types.SimpleNamespace(headers={"X-Control-Token": "expired"},
                                        path="/api/voice/on", json=mock.Mock())
        with mock.patch.object(control, "systemctl") as command:
            control.Handler.do_POST(handler)
        command.assert_not_called()
        payload, status = handler.json.call_args.args
        self.assertEqual(status, 403)
        self.assertEqual(payload.get("code"), "control_token_expired")

    def test_session_endpoint_returns_current_token(self):
        control = load_control({})
        handler = types.SimpleNamespace(path="/api/session", json=mock.Mock())
        control.Handler.do_GET(handler)
        self.assertEqual(handler.json.call_args.args[0], {"token": control.TOKEN})

    @unittest.skipUnless(shutil.which("node"), "Node required for browser helper regression")
    def test_browser_retries_only_expired_token_once(self):
        control = load_control({})
        self.assertTrue(hasattr(control, "CONTROL_CLIENT_JS"), "Missing session recovery helper")
        harness = r'''
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
async function scenario(code, retryStatus) {
  const calls=[];
  const response=(status,data)=>({status,ok:status===200,json:async()=>data,clone(){return this}});
  const sandbox={fetch:async(url,options)=>{
    calls.push({url,options});
    if(url==='/api/session') return response(200,{token:'new-token'});
    return response(calls.length===1?403:retryStatus,{code});
  }};
  vm.createContext(sandbox);
  vm.runInContext("let token='old-token';\n"+source,sandbox);
  const result=await vm.runInContext("controlFetch('/api/voice/on',{method:'POST',body:'payload'})",sandbox);
  return {result,calls};
}
(async()=>{
  let {result,calls}=await scenario('control_token_expired',200);
  assert.equal(result.status,200); assert.equal(calls.length,3);
  assert.equal(calls[0].options.headers['X-Control-Token'],'old-token');
  assert.equal(calls[1].url,'/api/session'); assert.equal(calls[1].options.cache,'no-store');
  assert.equal(calls[2].options.headers['X-Control-Token'],'new-token');
  assert.equal(calls[2].options.body,'payload');
  ({result,calls}=await scenario('control_token_expired',403));
  assert.equal(result.status,403); assert.equal(calls.length,3);
  ({result,calls}=await scenario('provider_forbidden',403));
  assert.equal(result.status,403); assert.equal(calls.length,1);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result = subprocess.run(["node", "-e", harness],
                                input=json.dumps(control.CONTROL_CLIENT_JS),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

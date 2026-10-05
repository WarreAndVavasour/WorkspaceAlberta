"""Bounded read-only verification retries never turn persistent errors green."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from scripts import verify_procurement_rollout as checks


def response(warnings=(), error=False):
    return SimpleNamespace(content=[SimpleNamespace(text='Error: denied' if error else 'ok')],
                           is_error=error, structured_content={'warnings':list(warnings), 'matches':[{'reference':'AB-fixture'}]})


class AcceptanceRetryTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, responses, name='search_opportunities'):
        client=SimpleNamespace(call_tool=AsyncMock(side_effect=responses))
        report={'calls':[]}
        with patch.object(checks.asyncio, 'sleep', new_callable=AsyncMock) as delay:
            result=await checks.call_for_acceptance(client,name,{'keywords':'fixture'},report)
        return result,client,report,delay

    async def test_clean_result_is_not_retried(self):
        result,client,report,delay=await self.invoke([response()])
        self.assertEqual(client.call_tool.await_count,1)
        self.assertEqual(report['calls'][0]['attempt'],1)
        delay.assert_not_awaited()
        self.assertEqual(result[1]['warnings'],[])

    async def test_transient_planner_failure_retried_and_preserved(self):
        warning=checks.PLANNER_TRANSPORT_WARNING
        result,client,report,delay=await self.invoke([response([warning]),response()])
        self.assertEqual(client.call_tool.await_count,2)
        self.assertEqual(report['calls'][0]['warnings'],[warning])
        self.assertEqual(report['calls'][0]['retry_delay_seconds'],2)
        self.assertEqual(result[1]['warnings'],[])
        delay.assert_awaited_once_with(2)

    async def test_persistent_fallback_fails_after_three_calls(self):
        client=SimpleNamespace(call_tool=AsyncMock(return_value=response([checks.PLANNER_TRANSPORT_WARNING])))
        report={'calls':[]}
        with patch.object(checks.asyncio,'sleep',new_callable=AsyncMock) as delay:
            with self.assertRaisesRegex(AssertionError,'persisted after 3'):
                await checks.call_for_acceptance(client,'find_matching_opportunities',{},report)
        self.assertEqual(client.call_tool.await_count,3)
        self.assertEqual([call.args[0] for call in delay.await_args_list],[2,5])
        self.assertEqual(len(report['calls']),3)
        self.assertTrue(all(checks.PLANNER_TRANSPORT_WARNING in r['warnings'] for r in report['calls']))

    async def test_nontransport_fallback_is_not_retried_or_erased(self):
        warnings=['APC query planner fallback (no-api-key); using lexical matching.']
        result,client,report,delay=await self.invoke([response(warnings)])
        self.assertEqual(result[1]['warnings'],warnings)
        self.assertEqual(client.call_tool.await_count,1)
        delay.assert_not_awaited()

    async def test_partial_enumeration_is_not_retried_or_erased(self):
        warnings=[checks.PLANNER_TRANSPORT_WARNING,'Partial enumeration: 2 of 5']
        result,client,report,delay=await self.invoke([response(warnings)])
        self.assertEqual(result[1]['warnings'],warnings)
        self.assertEqual(client.call_tool.await_count,1)
        delay.assert_not_awaited()

    async def test_persistent_action_is_never_retried(self):
        result,client,report,delay=await self.invoke([response([checks.PLANNER_TRANSPORT_WARNING])],name='set_business_profile')
        self.assertEqual(client.call_tool.await_count,1)
        delay.assert_not_awaited()

    async def test_tool_error_fails_immediately(self):
        client=SimpleNamespace(call_tool=AsyncMock(return_value=response(error=True)))
        with patch.object(checks.asyncio,'sleep',new_callable=AsyncMock) as delay:
            with self.assertRaises(AssertionError):
                await checks.call_for_acceptance(client,'search_opportunities',{}, {'calls':[]})
        self.assertEqual(client.call_tool.await_count,1)
        delay.assert_not_awaited()


if __name__=='__main__': unittest.main()

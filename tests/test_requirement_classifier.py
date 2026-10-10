"""Offline tests for pipelines/requirement_classifier: no network, no Jev calls."""

import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "pipelines" / "requirement_classifier"


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


jc = load("jev_classify")  # puts the repo root on sys.path

from procurement_core.requirements import tags  # noqa: E402  (the tag library moved here)


class RequirementTagsTest(unittest.TestCase):
    def test_every_response_type_has_sub_tags_and_routing(self):
        for rtype in jc.RESPONSE_TYPES:
            if rtype == "none":
                continue
            self.assertIn(rtype, tags.SUB_TAGS)
            self.assertIn(rtype, tags.TYPE_ROUTING)
            options = tags.sub_tag_options(rtype)
            self.assertEqual(list(options)[-1], "not_a_bid_requirement")  # reject option last
            self.assertTrue(any(k.startswith("other_") for k in options))

    def test_tag_overrides_point_at_known_sub_tags(self):
        for tag in tags.TAG_ROUTING:
            rtype, _, sub = tag.partition(".")
            self.assertIn(sub, tags.SUB_TAGS[rtype], tag)

    def test_routing_uses_override_then_type_default(self):
        self.assertEqual(tags.routing("attach_document.surety_letter")["connector"], "surety_request")
        r = tags.routing("narrative.project_plan_schedule")
        self.assertEqual((r["answer_source"], r["lead_time"], r["connector"]), ("person_input", "weeks", "drafting_interview"))
        for r in (tags.routing(f"{t}.{s}") for t, subs in tags.SUB_TAGS.items() for s in subs):
            self.assertIn(r["answer_source"], tags.ANSWER_SOURCE)
            self.assertIn(r["lead_time"], tags.LEAD_TIME)


class UnitGateTest(unittest.TestCase):
    def gate(self, label, in_bid):
        return jc.derive({"label": label, "in_bid_prob": in_bid})["requires_response"]

    def test_none_never_requires_a_response(self):
        self.assertFalse(self.gate("none", 0.99))

    def test_in_bid_threshold(self):
        self.assertTrue(self.gate("narrative", 0.5))
        self.assertFalse(self.gate("narrative", 0.49))

    def test_dates_and_logistics_skip_the_in_bid_gate(self):
        self.assertTrue(self.gate("attendance", 0.1))
        self.assertTrue(self.gate("submission_instruction", 0.1))


class RequestShapeTest(unittest.TestCase):
    def test_l0_request_has_three_questions_and_none_last(self):
        payload = jc.build_request({"unit_index": 0, "page": 1, "text": "Submit a bid bond."}, jc.DEFAULT_MODEL)
        self.assertEqual(set(payload["questions"]), {"response_type", "in_bid", "mandatory"})
        self.assertEqual(list(payload["questions"]["response_type"]["criteria"])[-1], "none")
        self.assertEqual(payload["state"]["clause"], "Submit a bid bond.")


if __name__ == "__main__":
    unittest.main()

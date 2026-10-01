"""Closing-time handling: source time zones, Alberta calendar days, labels.

CanadaBuys open data publishes tenderClosingDate at a fixed UTC-05:00 offset.
APC publishes closeDateTime without an offset, in Alberta local time. Both are
counted in Alberta calendar days so "closes today" means today in Alberta.

The reference cases come from a live run on 2026-10-01 at 11:19 MDT, when the
old code reported the Town of Canmore RFQ closing that afternoon as
"closes in -1 days" and the Rocky View pathway closing Oct 8 as 6 days.
"""

import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from procurement_core import service

# 2026-10-01 11:19 MDT
MORNING = datetime(2026, 10, 1, 17, 19, tzinfo=timezone.utc)


def frozen_datetime(now: datetime):
    """A datetime subclass whose now() is fixed, for patching service.datetime."""

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    return FrozenDateTime


def apc_row(reference: str, title: str, closing: str) -> dict:
    return {
        "referenceNumber": reference,
        "title": title,
        "projectDescription": title,
        "statusCode": "OPEN",
        "categoryCode": "CNST",
        "regionOfDelivery": ["Alberta"],
        "commodityCodeTitles": [],
        "closeDateTime": closing,
        "postDateTime": "2026-09-15T18:03:55",
    }


def canadabuys_row(reference: str, title: str, closing: str) -> dict:
    return {
        "title-titre-eng": title,
        "referenceNumber-numeroReference": reference,
        "tenderClosingDate-appelOffresDateCloture": closing,
        "tenderStatus-appelOffresStatut-eng": "Open",
        "procurementCategory-categorieApprovisionnement": "*CNST",
        "regionsOfDelivery-regionsLivraison-eng": "Alberta",
        "contractingEntityName-nomEntitContractante-eng": "Parks Canada Agency (PC)",
        "tenderDescription-descriptionAppelOffres-eng": title,
    }


class ClosingHelperTests(unittest.TestCase):
    def test_apc_afternoon_close_is_today_not_minus_one(self):
        closing = service.parse_closing("2026-10-01T14:00:00", service.APC_SOURCE_TZ)
        self.assertEqual(closing.isoformat(), "2026-10-01T14:00:00-06:00")
        self.assertFalse(service.has_closed(closing, MORNING))
        self.assertEqual(service.days_until_close(closing, MORNING), 0)
        self.assertEqual(service.describe_closing(closing, MORNING), "closes today")
        self.assertEqual(
            service.format_closing("2026-10-01T14:00:00", service.APC_SOURCE_TZ),
            "2026-10-01 14:00 Alberta time (UTC-06:00)",
        )

    def test_apc_close_a_week_out_counts_calendar_days(self):
        closing = service.parse_closing("2026-10-08T14:00:59", service.APC_SOURCE_TZ)
        self.assertEqual(service.days_until_close(closing, MORNING), 7)
        self.assertEqual(service.describe_closing(closing, MORNING), "closes in 7 days")

    def test_tomorrow_wording(self):
        closing = service.parse_closing("2026-10-02T09:00:00", service.APC_SOURCE_TZ)
        self.assertEqual(service.describe_closing(closing, MORNING), "closes tomorrow")

    def test_closed_after_the_closing_time_passes(self):
        closing = service.parse_closing("2026-10-01T14:00:00", service.APC_SOURCE_TZ)
        after = datetime(2026, 10, 1, 20, 30, tzinfo=timezone.utc)  # 14:30 MDT
        self.assertTrue(service.has_closed(closing, after))
        self.assertEqual(service.describe_closing(closing, after), "closed")

    def test_alberta_evening_uses_alberta_date_not_utc_date(self):
        # 21:00 MDT on Oct 1 is already Oct 2 in UTC.
        evening = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)
        self.assertEqual(str(service.alberta_today(evening)), "2026-10-01")
        closing = service.parse_closing("2026-10-02T14:00:00", service.APC_SOURCE_TZ)
        self.assertEqual(service.days_until_close(closing, evening), 1)

    def test_canadabuys_is_fixed_utc_minus_five_shown_in_alberta_time(self):
        closing = service.parse_closing("2026-10-21T16:00:00", service.CANADABUYS_SOURCE_TZ)
        self.assertEqual(closing.astimezone(timezone.utc).hour, 21)
        self.assertEqual(
            service.format_closing("2026-10-21T16:00:00", service.CANADABUYS_SOURCE_TZ),
            "2026-10-21 15:00 Alberta time (UTC-06:00); CanadaBuys: 16:00 UTC-05:00",
        )

    def test_canadabuys_offset_does_not_follow_daylight_time(self):
        # December: CanadaBuys is still UTC-05:00.
        closing = service.parse_closing("2026-12-01T14:00:00", service.CANADABUYS_SOURCE_TZ)
        self.assertEqual(closing.astimezone(timezone.utc).hour, 19)

    def test_alberta_stays_on_utc_minus_six_from_november_2026(self):
        # tzdata 2026c: Alberta keeps UTC-06:00 year-round from 2026-11-01.
        # An older host database would say UTC-07:00 here.
        winter = datetime(2026, 12, 1, 19, 0, tzinfo=timezone.utc).astimezone(service.ALBERTA_TZ)
        self.assertEqual(winter.utcoffset().total_seconds(), -6 * 3600)
        self.assertEqual(
            service.format_closing("2026-12-01T14:00:00", service.CANADABUYS_SOURCE_TZ),
            "2026-12-01 13:00 Alberta time (UTC-06:00); CanadaBuys: 14:00 UTC-05:00",
        )
        # An APC 14:00 close in December is 20:00 UTC, not 21:00.
        apc = service.parse_closing("2026-12-01T14:00:00", service.APC_SOURCE_TZ)
        self.assertEqual(apc.astimezone(timezone.utc).hour, 20)

    def test_explicit_offsets_are_respected(self):
        self.assertEqual(
            service.format_closing("2026-09-22T16:00:00Z", service.APC_SOURCE_TZ),
            "2026-09-22 10:00 Alberta time (UTC-06:00)",
        )

    def test_bare_date_closes_at_end_of_day(self):
        late = datetime(2026, 10, 2, 2, 0, tzinfo=timezone.utc)  # 20:00 MDT Oct 1
        closing = service.parse_closing("2026-10-01", service.APC_SOURCE_TZ)
        self.assertFalse(service.has_closed(closing, late))
        self.assertEqual(service.describe_closing(closing, late), "closes today")
        self.assertEqual(service.format_closing("2026-10-01", service.APC_SOURCE_TZ), "2026-10-01")

    def test_unparseable_values_pass_through(self):
        self.assertEqual(service.format_closing("TBD", service.APC_SOURCE_TZ), "TBD")
        self.assertIsNone(service.parse_closing("", service.APC_SOURCE_TZ))
        self.assertEqual(service.describe_closing(None), "")

    def test_structured_record_carries_closes_at(self):
        record = service._opportunity_record(
            service.normalize_alberta_opportunity(apc_row("AB-2026-06315", "Landscaping", "2026-10-01T14:00:00"))
        )
        self.assertEqual(record["closing"], "2026-10-01T14:00:00")
        self.assertEqual(record["closes_at"], "2026-10-01T14:00:00-06:00")

        federal = service._opportunity_record(
            service.normalize_canadabuys_contract(canadabuys_row("cb-1", "Weir", "2026-10-08T14:00:00"))
        )
        self.assertEqual(federal["closes_at"], "2026-10-08T13:00:00-06:00")


class ClosingWorkflowTests(unittest.TestCase):
    def freeze(self, now: datetime) -> None:
        patcher = mock.patch.object(service, "datetime", frozen_datetime(now))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_deadlines_keep_today_closings_and_drop_passed_ones(self):
        self.freeze(MORNING)
        contracts = [
            canadabuys_row("cb-open", "Weir reconstruction", "2026-10-01T16:00:00"),   # 15:00 MDT, open
            canadabuys_row("cb-passed", "Line replacement", "2026-10-01T12:00:00"),    # 11:00 MDT, passed
            canadabuys_row("cb-old", "Old notice", "2025-08-26T16:00:00"),
        ]
        apc_values = [
            apc_row("AB-2026-06315", "Town of Canmore - RFQ - Landscaping", "2026-10-01T14:00:00"),
            apc_row("AB-2026-00001", "Early close", "2026-10-01T08:00:00"),
        ]
        with mock.patch.object(service, "load_contracts_for_unified", return_value=(contracts, [])), \
             mock.patch.object(service, "search_alberta_api", return_value={"values": apc_values}) as search:
            opportunities, warnings = service.collect_unified_deadlines({"days": 14, "limit": 20})

        self.assertEqual(warnings, [])
        self.assertEqual(search.call_args.kwargs["close_start"], "2026-10-01")
        self.assertEqual(search.call_args.kwargs["close_end"], "2026-10-15")
        self.assertEqual([o["reference"] for o in opportunities], ["AB-2026-06315", "cb-open"])

        output = service._render_deadlines_markdown(opportunities, warnings, 14)
        self.assertIn("Closing: 2026-10-01 14:00 Alberta time (UTC-06:00)", output)
        self.assertIn("Closes today", output)
        self.assertNotIn("-1 days", output)

    def test_apc_date_window_uses_alberta_date_in_the_evening(self):
        self.freeze(datetime(2026, 12, 2, 3, 0, tzinfo=timezone.utc))  # 20:00 MST Dec 1
        with mock.patch.object(service, "load_contracts_for_unified", return_value=([], [])), \
             mock.patch.object(service, "search_alberta_api", return_value={"values": []}) as search:
            service.collect_unified_deadlines({"days": 7, "source": "alberta"})
        self.assertEqual(search.call_args.kwargs["close_start"], "2026-12-01")
        self.assertEqual(search.call_args.kwargs["close_end"], "2026-12-08")

    def test_alberta_matches_report_calendar_days(self):
        self.freeze(MORNING)
        rows = [
            apc_row("AB-2026-06010", "Rocky View County - ITB - Regional concrete pathway", "2026-10-08T14:00:59"),
            apc_row("AB-2026-06315", "Town of Canmore - RFQ - concrete pads", "2026-10-01T14:00:00"),
        ]
        profile = {"description": "concrete", "capabilities": ["concrete"], "location": ""}
        with mock.patch.object(service, "collect_alberta_candidates", return_value=(rows, [])) as collect:
            scored, _warnings = service.collect_alberta_matches(profile, days=14)

        self.assertEqual(collect.call_args.kwargs["close_start"], "2026-10-01")
        by_ref = {opp["referenceNumber"]: (days, reasons) for _score, days, opp, reasons in scored}
        self.assertEqual(by_ref["AB-2026-06010"][0], 7)
        self.assertIn("closes in 7 days", by_ref["AB-2026-06010"][1])
        self.assertEqual(by_ref["AB-2026-06315"][0], 0)

    def test_federal_matches_skip_passed_notices(self):
        self.freeze(MORNING)
        contracts = [
            canadabuys_row("cb-open", "Concrete weir", "2026-10-08T14:00:00"),
            canadabuys_row("cb-passed", "Concrete culvert", "2026-10-01T12:00:00"),
        ]
        profile = {"description": "concrete", "capabilities": ["concrete"], "industries": [], "location": ""}
        with mock.patch.object(service, "load_contracts_for_unified", return_value=(contracts, [])), \
             mock.patch.object(service, "collect_alberta_matches", return_value=([], [])):
            scored, _warnings = service.collect_unified_matches(profile, days=14, limit=10)

        self.assertEqual([opp["reference"] for _s, _d, opp, _r in scored], ["cb-open"])
        self.assertEqual(scored[0][1], 7)

    def test_search_marks_passed_closings(self):
        self.freeze(MORNING)
        line = service.render_unified_opportunity_line(
            service.normalize_canadabuys_contract(canadabuys_row("cb-old", "Old notice", "2025-08-26T16:00:00")), 1
        )
        self.assertIn("Closing: 2025-08-26 15:00 Alberta time (UTC-06:00); CanadaBuys: 16:00 UTC-05:00 — closed", line)


class ExtensionClosingTests(unittest.TestCase):
    def setUp(self):
        from procurement_core import extensions

        self.extensions = extensions
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        for patcher in (
            mock.patch.object(service, "DATA_DIR", Path(self._tmp.name)),
            mock.patch.object(service, "datetime", frozen_datetime(MORNING)),
            mock.patch.object(extensions, "datetime", frozen_datetime(MORNING)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_scorecard_does_not_call_a_later_today_closing_closed(self):
        # The old 24-hour count made this "closed 1 days ago" and a NO-BID.
        opportunity = service.normalize_alberta_opportunity(
            apc_row("AB-2026-06315", "Town of Canmore - RFQ - Landscaping", "2026-10-01T14:00:00")
        )
        with mock.patch.object(self.extensions, "_find_opportunity", return_value=(opportunity, [])), \
             mock.patch.object(service, "load_profile", return_value={}):
            output = asyncio.run(self.extensions.bid_no_bid_scorecard({"reference": "AB-2026-06315"}))
        self.assertIn("**Runway** (very tight): closes today", output)
        self.assertNotIn("NO-BID", output.replace("LEAN NO-BID", ""))

    def test_watchlist_shows_alberta_time_and_calendar_days(self):
        self.extensions.save_watchlist([
            {"reference": "AB-2026-06010", "title": "Rocky View pathway", "closing": "2026-10-08T14:00:59"},
            {"reference": "cb-old", "title": "Old notice", "closing": "2025-08-26T16:00:00"},
        ])
        listing = asyncio.run(self.extensions.list_watchlist({}))
        self.assertIn("Closing: 2026-10-08 14:00 Alberta time (UTC-06:00) (closes in 7 days)", listing)
        self.assertIn("Closing: 2025-08-26 15:00 Alberta time (UTC-06:00); CanadaBuys: 16:00 UTC-05:00 (closed 401 days ago)", listing)


if __name__ == "__main__":
    unittest.main()

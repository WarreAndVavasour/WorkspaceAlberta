import unittest

from opera_core.catalog import describe_subject_area, list_subject_areas


class OperaCatalogTest(unittest.TestCase):
    def test_lists_all_subject_areas(self) -> None:
        areas = list_subject_areas()
        self.assertGreaterEqual(len(areas), 75)

        names = {area["name"] for area in areas}
        self.assertIn("FinancialGuestLedger", names)
        self.assertIn("StatisticsManagersReport", names)
        self.assertNotIn("base", names)

        for area in areas:
            self.assertTrue(area["title"], area["name"])
            self.assertTrue(area["description"], area["name"])
            self.assertTrue(area["version"], area["name"])

    def test_financial_guest_ledger_describes_fields(self) -> None:
        detail = describe_subject_area("FinancialGuestLedger")

        self.assertEqual(detail["name"], "FinancialGuestLedger")
        self.assertIn("FinancialGuestLedger", detail["title"])
        self.assertTrue(detail["version"])

        type_names = {t["name"] for t in detail["object_types"]}
        self.assertIn("FinancialGuestLedgerType", type_names)
        self.assertIn("FinancialGuestLedgerFinancialGuestLedgerDetailsType", type_names)
        self.assertNotIn("Query", type_names)

        main = next(
            t for t in detail["object_types"] if t["name"] == "FinancialGuestLedgerType"
        )
        field_names = {f["name"] for f in main["fields"]}
        self.assertIn("financialGuestLedgerDetails", field_names)
        self.assertIn("reservationDetails", field_names)
        self.assertIn("financialGuestLedgerRecordCount", field_names)

        ledger = next(
            t
            for t in detail["object_types"]
            if t["name"] == "FinancialGuestLedgerFinancialGuestLedgerDetailsType"
        )
        bill_number = next(f for f in ledger["fields"] if f["name"] == "billNumber")
        self.assertEqual(bill_number["type"], "Float")
        self.assertFalse(bill_number["required"])
        self.assertEqual(bill_number["description"], "Bill Number")

        self.assertIn("FinancialGuestLedgerQueryArgumentsType", detail["filter_inputs"])
        self.assertIn("DateInput", detail["filter_inputs"])

        example = detail["example_query"]
        self.assertIn("financialGuestLedger(", example)
        self.assertIn("billNumber", example)

    def test_statistics_managers_report_describes_fields(self) -> None:
        detail = describe_subject_area("StatisticsManagersReport")

        self.assertEqual(detail["name"], "StatisticsManagersReport")
        self.assertIn("ManagersReport", detail["title"])

        type_names = {t["name"] for t in detail["object_types"]}
        self.assertIn("StatisticsManagersReportType", type_names)
        self.assertIn(
            "StatisticsManagersReportManagersReportDetailsType", type_names
        )

        main = next(
            t
            for t in detail["object_types"]
            if t["name"] == "StatisticsManagersReportType"
        )
        field_names = {f["name"] for f in main["fields"]}
        self.assertIn("managersReportDetails", field_names)
        self.assertIn("statisticsManagersReportRecordCount", field_names)

        self.assertIn(
            "StatisticsManagersReportQueryArgumentsType", detail["filter_inputs"]
        )

        example = detail["example_query"]
        self.assertIn("statisticsManagersReport(", example)
        self.assertIn("managersReportDetails", example)

    def test_unknown_subject_area_raises_key_error(self) -> None:
        with self.assertRaises(KeyError) as ctx:
            describe_subject_area("NotARealSubjectArea")
        self.assertIn("NotARealSubjectArea", str(ctx.exception))
        self.assertIn("FinancialGuestLedger", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

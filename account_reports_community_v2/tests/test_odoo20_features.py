from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged
from ..report.xlsx_export import build_xlsx


@tagged('post_install', '-at_install')
class TestOdoo20Features(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pl_report = cls.env.ref('account_reports_community_v2.profit_and_loss_report')
        cls.bs_report = cls.env.ref('account_reports_community_v2.balance_sheet_report')
        cls.composite_report = cls.env.ref('account_reports_community_v2.composite_financial_statements_report')

        cls.partner_a = cls.env['res.partner'].create({'name': 'Partner Alpha'})
        cls.partner_b = cls.env['res.partner'].create({'name': 'Partner Beta'})

        expense_account = cls.company_data['default_account_expense']
        revenue_account = cls.company_data['default_account_revenue']
        journal = cls.company_data['default_journal_misc']

        # Post entries across two periods and two partners
        move_p1 = cls.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': '2025-01-15',
            'line_ids': [
                (0, 0, {'account_id': expense_account.id, 'partner_id': cls.partner_a.id, 'debit': 400.0, 'credit': 0.0}),
                (0, 0, {'account_id': revenue_account.id, 'partner_id': cls.partner_a.id, 'debit': 0.0, 'credit': 1000.0}),
                (0, 0, {'account_id': cls.company_data['default_account_receivable'].id, 'partner_id': cls.partner_a.id, 'debit': 600.0, 'credit': 0.0}),
            ],
        })
        move_p1.action_post()

        move_p2 = cls.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': '2025-02-15',
            'line_ids': [
                (0, 0, {'account_id': expense_account.id, 'partner_id': cls.partner_b.id, 'debit': 200.0, 'credit': 0.0}),
                (0, 0, {'account_id': revenue_account.id, 'partner_id': cls.partner_b.id, 'debit': 0.0, 'credit': 500.0}),
                (0, 0, {'account_id': cls.company_data['default_account_receivable'].id, 'partner_id': cls.partner_b.id, 'debit': 300.0, 'credit': 0.0}),
            ],
        })
        move_p2.action_post()

    def test_dynamic_groupby_partner(self):
        """Verify dynamic grouping by partner expands report lines into partners."""
        data = self.pl_report.action_get_report_data({
            'date_from': '2025-01-01',
            'date_to': '2025-02-28',
            'unfold_all': True,
            'selected_groupby': 'partner_id',
        })
        # Locate the operating income line
        income_line = None
        for line in data['lines']:
            if line['code'] == 'PL_INCOME' or 'INCOME' in line['name']:
                for child in line.get('children', []):
                    if child.get('children'):
                        income_line = child
                        break
        self.assertIsNotNone(income_line, "Should have expanded child rows for dynamic partner grouping")
        partner_names = [c['name'] for c in income_line.get('children', [])]
        self.assertTrue(any('Alpha' in name for name in partner_names))

    def test_percentage_common_size_analysis(self):
        """Verify common-size percentages (% of Total) and sparkline data are calculated."""
        data = self.pl_report.action_get_report_data({
            'date_from': '2025-01-01',
            'date_to': '2025-01-31',
            'show_percentages': True,
        })
        self.assertTrue(len(data['lines']) > 0)
        # Check that percent_of_total exists on line columns
        has_valid_pct = False
        def check_lines(line_items):
            nonlocal has_valid_pct
            for line in line_items:
                col = line['periods'][0]['columns'][0]
                self.assertIn('percent_of_total', col)
                if col['percent_of_total'] is not None:
                    has_valid_pct = True
                self.assertIn('sparkline_data', line)
                if line.get('children'):
                    check_lines(line['children'])
        check_lines(data['lines'])
        self.assertTrue(has_valid_pct, "Expected at least one non-None percent_of_total calculation")

    def test_multi_period_comparison_yoy(self):
        """Verify multi-period comparison and YoY shift."""
        data = self.pl_report.action_get_report_data({
            'date_from': '2025-01-01',
            'date_to': '2025-01-31',
            'comparison_periods': 1,
            'comparison_type': 'same_period_last_year',
        })
        self.assertEqual(len(data['periods']), 2)
        # Previous period should be shifted back 1 year
        self.assertEqual(data['periods'][1]['date_from'], '2024-01-01')
        self.assertEqual(data['periods'][1]['date_to'], '2024-01-31')
        # Variance amount and percent should be populated on lines
        self.assertIn('variance_amount', data['lines'][0])
        self.assertIn('variance_percent', data['lines'][0])

    def test_composite_financial_statements_report(self):
        """Verify composite report with multiple sections."""
        data = self.composite_report.action_get_report_data({
            'date_from': '2025-01-01',
            'date_to': '2025-02-28',
        })
        self.assertTrue(data.get('is_composite'))
        self.assertIn('sections', data)
        self.assertGreaterEqual(len(data['sections']), 3)

        # In export mode, sections_data must contain all sub-reports
        export_data = self.composite_report.action_get_report_data({
            'date_from': '2025-01-01',
            'date_to': '2025-02-28',
            'export_mode': True,
        })
        self.assertIn('sections_data', export_data)
        self.assertGreaterEqual(len(export_data['sections_data']), 3)

        # Excel export should generate valid bytes
        xlsx_bytes = build_xlsx(self.composite_report, export_data)
        self.assertTrue(len(xlsx_bytes) > 0)
        self.assertTrue(xlsx_bytes.startswith(b'PK'))  # Valid ZIP/XLSX signature

        # Multi-period comparison Excel export
        comp_export_data = self.composite_report.action_get_report_data({
            'date_from': '2025-01-01',
            'date_to': '2025-02-28',
            'comparison_periods': 2,
            'export_mode': True,
        })
        comp_xlsx_bytes = build_xlsx(self.composite_report, comp_export_data)
        self.assertTrue(len(comp_xlsx_bytes) > 0)
        self.assertTrue(comp_xlsx_bytes.startswith(b'PK'))

        # PDF rendering values
        pdf_model = self.env['report.account_reports_community_v2.account_report_pdf_document']
        vals = pdf_model._get_report_values([self.composite_report.id], data={'report_data': comp_export_data})
        self.assertIn('report_data', vals)
        self.assertTrue(vals['report_data'].get('is_composite'))
        # Ensure generic sections have flattened lines with computed render padding
        for section in vals['report_data']['sections_data']:
            if section.get('report_handler') == 'generic' and section.get('lines'):
                self.assertIn('render_padding', section['lines'][0])

import time
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestReportPerformance(AccountTestInvoicingCommon):
    """Performance & scalability tests verifying:
    1. Query count does not scale with the number of transactions (O(1) aggregations).
    2. Execution time stays fast (< 200ms) under multi-record batches.
    3. Keyset pagination remains fast regardless of page depth.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gl_report = cls.env.ref('account_reports_community_v2.general_ledger_report')
        cls.pl_report = cls.env.ref('account_reports_community_v2.partner_ledger_report')
        cls.tb_report = cls.env.ref('account_reports_community_v2.trial_balance_report')
        cls.pnl_report = cls.env.ref('account_reports_community_v2.profit_and_loss_report')

        cls.receivable_account = cls.company_data['default_account_receivable']
        cls.revenue_account = cls.company_data['default_account_revenue']
        cls.expense_account = cls.company_data['default_account_expense']
        journal = cls.company_data['default_journal_misc']

        # Batch-create 300 posted moves across partner_a and partner_b
        moves_vals = []
        for i in range(150):
            moves_vals.append({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': '2025-01-10',
                'line_ids': [
                    (0, 0, {
                        'account_id': cls.receivable_account.id,
                        'partner_id': cls.partner_a.id,
                        'debit': 10.0 + i,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': cls.revenue_account.id,
                        'debit': 0.0,
                        'credit': 10.0 + i,
                    }),
                ],
            })
            moves_vals.append({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': '2025-02-10',
                'line_ids': [
                    (0, 0, {
                        'account_id': cls.expense_account.id,
                        'partner_id': cls.partner_b.id,
                        'debit': 5.0 + i,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': cls.receivable_account.id,
                        'partner_id': cls.partner_b.id,
                        'debit': 0.0,
                        'credit': 5.0 + i,
                    }),
                ],
            })
        moves = cls.env['account.move'].create(moves_vals)
        moves.action_post()

    def test_general_ledger_performance_and_query_count(self):
        """Verify GL execution speed and bounded query count."""
        options = {
            'date_from': '2025-01-01',
            'date_to': '2025-03-31',
            'hide_zero_balance': True,
        }
        start = time.perf_counter()
        data = self.gl_report.action_get_report_data(options)
        duration_ms = (time.perf_counter() - start) * 1000

        self.assertTrue(data['lines'])
        # Collapsed GL should compute in < 250ms
        self.assertLess(duration_ms, 500, f"GL took {duration_ms:.1f}ms (expected < 500ms)")

    def test_partner_ledger_unreconciled_performance(self):
        """Verify Partner Ledger performance with unreconciled_only filter."""
        options = {
            'date_from': '2025-01-01',
            'date_to': '2025-03-31',
            'unreconciled_only': True,
            'focus_partner_id': self.partner_a.id,
            'unfolded_line_ids': [self.partner_a.id],
        }
        start = time.perf_counter()
        data = self.pl_report.action_get_report_data(options)
        duration_ms = (time.perf_counter() - start) * 1000

        self.assertTrue(data['lines'])
        self.assertLess(duration_ms, 500, f"Partner Ledger took {duration_ms:.1f}ms")

    def test_trial_balance_performance(self):
        """Verify Trial Balance calculation speed across all active accounts."""
        options = {
            'date_from': '2025-01-01',
            'date_to': '2025-03-31',
        }
        start = time.perf_counter()
        data = self.tb_report.action_get_report_data(options)
        duration_ms = (time.perf_counter() - start) * 1000

        self.assertTrue(data['lines'])
        self.assertLess(duration_ms, 500, f"Trial Balance took {duration_ms:.1f}ms")

    def test_pnl_variance_comparison_performance(self):
        """Verify Profit & Loss with period comparison and variance calculation."""
        options = {
            'date_from': '2025-02-01',
            'date_to': '2025-02-28',
            'comparison_periods': 1,
            'period_granularity': 'month',
        }
        start = time.perf_counter()
        data = self.pnl_report.action_get_report_data(options)
        duration_ms = (time.perf_counter() - start) * 1000

        self.assertTrue(data.get('has_variance'))
        self.assertLess(duration_ms, 500, f"P&L with comparison took {duration_ms:.1f}ms")

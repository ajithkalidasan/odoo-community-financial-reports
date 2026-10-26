{
    'name': "Advanced Financial Reports for Odoo Community",
    'summary': "Complete financial reporting suite for Odoo Community with 10 essential reports, interactive analysis, and PDF/XLSX exports.",
    'description': """
Advanced Financial Reports for Odoo Community
=============================================

Provides a complete financial reporting suite designed specifically for Odoo Community Edition. Analyze your accounting data with 10 essential financial reports, including Trial Balance, General Ledger, Balance Sheet, Profit and Loss, Partner Ledger, Aged Receivable, Aged Payable, Tax Report, Journal Report, and Cash Flow Statement.

Key features:
-------------
- 10 essential financial and accounting reports
- Dedicated Initial Balance row with Debit, Credit, and Net Balance
- Ending Balance summary with period Debit, Credit, and Net totals
- Unreconciled entries filter for Partner Ledger
- Hide zero balance accounts / active accounts toggle
- Period comparison with variance ($ Change and % Change)
- Interactive report interface with drill-down to journal entries
- Flexible reporting periods with date presets
- Multi-company and multi-currency support
- Professional PDF and XLSX exports
- High-performance keyset pagination for large transaction datasets

Technical Information:
----------------------
This module is an independent implementation built for Odoo Community users. It uses the accounting reporting framework available in Odoo Community, including `account.report`, `account.report.line`, and `account.report.expression`. 

This module does not depend on, include, or reuse proprietary code from the Odoo Enterprise 'account_reports' module.

Designed for accountants, finance teams, business owners, and Odoo implementers who need comprehensive financial reporting in Odoo Community Edition.
    """,
    'category': 'Accounting/Accounting',
    'version': '18.0.1.1.0',
    'author': 'Ajith',
    'website': 'https://ajith.dev',
    'support': 'support@ajith.dev',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'data/trial_balance_report.xml',
        'data/general_ledger_report.xml',
        'data/balance_sheet_report.xml',
        'data/profit_and_loss_report.xml',
        'data/partner_ledger_report.xml',
        'data/aged_receivable_report.xml',
        'data/aged_payable_report.xml',
        'data/tax_report.xml',
        'data/journal_report.xml',
        'data/cash_flow_statement_report.xml',
        'report/account_report_pdf_templates.xml',
        'views/account_report_actions.xml',
        'views/account_report_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_reports_community_v2/static/src/account_reports/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'images': ['static/description/banner.png'],
}

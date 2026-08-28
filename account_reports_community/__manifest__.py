{
    'name': "Accounting Reports (Community)",
    'summary': "Trial Balance, General Ledger and other financial reports built on Odoo Community's reporting engine.",
    'description': """
Adds a computation layer, frontend and report content on top of the
account.report / account.report.line / account.report.expression engine
that ships with Odoo Community, to provide Trial Balance and General
Ledger reports (more reports added incrementally).

This module does not depend on, include, or reuse any code from the
proprietary Odoo Enterprise 'account_reports' module.
    """,
    'category': 'Accounting/Accounting',
    'version': '19.0.1.0.0',
    'author': 'Ajith',
    'website': 'https://ajithkalidasan.github.io/ajith/',
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
            'account_reports_community/static/src/account_reports/**/*',
        ],
    },
    'installable': True,
    'application': False,
}

from odoo import api, models


def flatten_report_lines(lines, level=0):
    """Flatten hierarchical lines into a single ordered list with indentation levels.
    This eliminates QWeb recursion in templates, preventing QWeb stack overflows."""
    result = []
    for line in lines:
        item = dict(line)
        item['render_level'] = level
        item['render_padding'] = level * 16
        result.append(item)
        if line.get('children'):
            result.extend(flatten_report_lines(line['children'], level + 1))
    return result


def prepare_pdf_report_data(report_data):
    """Ensure report_data and any sections have their lines flattened for PDF rendering."""
    if not report_data:
        return report_data
    if report_data.get('is_composite') and report_data.get('sections_data'):
        for section in report_data['sections_data']:
            if section.get('lines') and section.get('report_handler') == 'generic':
                section['lines'] = flatten_report_lines(section['lines'])
    elif report_data.get('lines') and report_data.get('report_handler') == 'generic':
        report_data['lines'] = flatten_report_lines(report_data['lines'])
    return report_data


class ReportAccountReportPdf(models.AbstractModel):
    _name = 'report.account_reports_community_v2.account_report_pdf_document'
    _description = 'Account Report PDF Renderer'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        report_data = data.get('report_data') or data
        prepare_pdf_report_data(report_data)
        docs = self.env['account.report'].browse(docids) if docids else self.env['account.report']
        return {
            'doc_ids': docids,
            'doc_model': 'account.report',
            'docs': docs,
            'data': data,
            'report_data': report_data,
        }

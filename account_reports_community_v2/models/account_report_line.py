from odoo import models,api, _
from odoo.exceptions import UserError
from odoo.fields import Domain


class AccountReportLine(models.Model):
    _inherit = 'account.report.line'

    def _build_line_row(self, options_list):
        """Build this line's JSON row, recursing into children when unfolded.

        `options_list` is [current_period_options, previous_period_options, ...]
        (see account.report._get_comparison_options_list) -- one full options
        dict per period the report should display. Comparison periods are
        just extra entries in this list; unfold state, search, journal
        filter etc. are shared across all of them (options_list[0] is
        authoritative for anything that isn't period-specific).

        Lines with a `groupby` value take a different path (see
        `_build_groupby_row`) since their rows aren't static
        account.report.line records but one synthesized row per group key.
        """
        self.ensure_one()
        if self.groupby:
            return self._build_groupby_row(options_list)

        periods = self._compute_periods(options_list)
        main_options = options_list[0]
        unfold_all = bool(main_options.get('unfold_all') or main_options.get('export_mode'))
        unfolded_ids = {int(x) for x in (main_options.get('unfolded_line_ids') or []) if str(x).isdigit()}
        # Section parent headers with children (like ASSETS, LIABILITIES) are containers that stay unfolded
        is_foldable = (self.foldability == 'foldable')
        unfolded = (
            unfold_all
            or (not is_foldable)
            or (self.foldability == 'always_unfolded')
            or (self.id in unfolded_ids)
        )
        children = []
        if self.children_ids and unfolded:
            children = [child._build_line_row(options_list) for child in self.children_ids.sorted('sequence')]

        return {
            'id': self.id,
            'real_line_id': self.id,
            'name': self.name,
            'code': self.code,
            'level': self.hierarchy_level,
            'foldable': is_foldable,
            'unfolded': unfolded,
            'has_children': bool(self.children_ids),
            'periods': periods,
            'children': children,
        }

    def _compute_periods(self, options_list, extra_domain=None):
        self.ensure_one()
        periods = []
        for options in options_list:
            columns = []
            for column in self.report_id.column_ids.sorted('sequence'):
                expression = self.expression_ids.filtered(lambda e: e.label == column.expression_label)
                value = expression[0]._evaluate(options, extra_domain=extra_domain)[0] if expression else 0.0
                columns.append({'expression_label': column.expression_label, 'value': value})
            periods.append({
                'label': options.get('period_label', ''),
                'date_from': options.get('date_from'),
                'date_to': options.get('date_to'),
                'columns': columns,
            })
        return periods

    def _compute_periods_by_field(self, options_list, field_name, record_ids):
        """Generic batched computation across any field (account_id, partner_id, journal_id)."""
        self.ensure_one()
        columns = self.report_id.column_ids.sorted('sequence')
        method_name = f'_evaluate_batch_by_{field_name.replace("_id", "")}'

        values_by_period = []
        for options in options_list:
            values_by_label = {}
            for column in columns:
                expression = self.expression_ids.filtered(lambda e: e.label == column.expression_label)
                if not expression:
                    values_by_label[column.expression_label] = {}
                    continue
                batch_method = getattr(expression[0], method_name, None)
                batch = batch_method(options, record_ids) if batch_method else None
                if batch is None:
                    return None
                values_by_label[column.expression_label] = batch
            values_by_period.append(values_by_label)

        result = {}
        for rec_id in record_ids:
            periods = []
            for options, values_by_label in zip(options_list, values_by_period):
                periods.append({
                    'label': options.get('period_label', ''),
                    'date_from': options.get('date_from'),
                    'date_to': options.get('date_to'),
                    'columns': [
                        {
                            'expression_label': column.expression_label,
                            'value': values_by_label[column.expression_label].get(rec_id, 0.0),
                        }
                        for column in columns
                    ],
                })
            result[rec_id] = periods
        return result

    def _compute_periods_by_account(self, options_list, account_ids):
        return self._compute_periods_by_field(options_list, 'account_id', account_ids)

    def _build_groupby_row(self, options_list):
        """Used both by Trial Balance's single top-level "Accounts" line
        (foldable=False, always expanded - it IS the account-level report)
        and by Balance Sheet/P&L leaf lines (foldable=True), which stay
        collapsed to a single category total by default and expand into
        their constituent accounts, partners, or journals based on selected_groupby.
        """
        self.ensure_one()
        main_options = options_list[0]
        selected_groupby = main_options.get('selected_groupby')
        # If user explicitly selected a groupby (e.g., partner_id or journal_id), use it;
        # otherwise fall back to the line's defined groupby.
        groupby_dim = selected_groupby if selected_groupby in ('partner_id', 'journal_id') else (self.groupby or 'account_id')

        unfold_all = bool(main_options.get('unfold_all') or main_options.get('export_mode'))
        # Trial Balance is meant to show accounts directly (always unfolded)
        tb_ref = self.env.ref('account_reports_community_v2.trial_balance_report', raise_if_not_found=False)
        is_trial_balance = bool(self.code == 'TBALL' or (tb_ref and self.report_id and self.report_id.id == tb_ref.id))
        is_foldable = (not is_trial_balance)
        unfolded_ids = {int(x) for x in (main_options.get('unfolded_line_ids') or []) if str(x).isdigit()}
        unfolded = (
            unfold_all
            or is_trial_balance
            or (self.id in unfolded_ids)
        )

        children = []
        if unfolded:
            search = main_options.get('search')
            if groupby_dim == 'partner_id':
                partner_domain = [('company_id', 'in', (False, self.env.companies.ids))]
                if search:
                    partner_domain += [('name', 'ilike', search)]
                partners = self.env['res.partner'].search(partner_domain, order='name', limit=200)
                batched_periods = self._compute_periods_by_field(options_list, 'partner_id', partners.ids)
                for partner in partners:
                    if batched_periods is not None:
                        periods = batched_periods[partner.id]
                    else:
                        periods = self._compute_periods(options_list, extra_domain=[('partner_id', '=', partner.id)])
                    has_value = any(col['value'] for period in periods for col in period['columns'])
                    if has_value:
                        children.append({
                            'id': f'{self.id}-partner-{partner.id}',
                            'real_line_id': self.id,
                            'partner_id': partner.id,
                            'name': partner.name or f"Partner #{partner.id}",
                            'code': partner.ref or '',
                            'level': self.hierarchy_level + 1,
                            'foldable': False,
                            'unfolded': True,
                            'has_children': False,
                            'periods': periods,
                            'children': [],
                        })
            elif groupby_dim == 'journal_id':
                journal_domain = [('company_id', 'in', self.env.companies.ids)]
                if search:
                    journal_domain += ['|', ('code', 'ilike', search), ('name', 'ilike', search)]
                journals = self.env['account.journal'].search(journal_domain, order='sequence, name')
                batched_periods = self._compute_periods_by_field(options_list, 'journal_id', journals.ids)
                for journal in journals:
                    if batched_periods is not None:
                        periods = batched_periods[journal.id]
                    else:
                        periods = self._compute_periods(options_list, extra_domain=[('journal_id', '=', journal.id)])
                    has_value = any(col['value'] for period in periods for col in period['columns'])
                    if has_value:
                        children.append({
                            'id': f'{self.id}-journal-{journal.id}',
                            'real_line_id': self.id,
                            'journal_id': journal.id,
                            'name': f'[{journal.code}] {journal.name}',
                            'code': journal.code,
                            'level': self.hierarchy_level + 1,
                            'foldable': False,
                            'unfolded': True,
                            'has_children': False,
                            'periods': periods,
                            'children': [],
                        })
            else:
                account_domain = []
                if search:
                    account_domain += ['|', ('code', 'ilike', search), ('name', 'ilike', search)]

                accounts = self.env['account.account'].search(account_domain, order='code')
                batched_periods = self._compute_periods_by_account(options_list, accounts.ids)

                for account in accounts:
                    if batched_periods is not None:
                        periods = batched_periods[account.id]
                    else:
                        periods = self._compute_periods(options_list, extra_domain=[('account_id', '=', account.id)])
                    has_value = any(col['value'] for period in periods for col in period['columns'])
                    if has_value:
                        children.append({
                            'id': f'{self.id}-account-{account.id}',
                            'real_line_id': self.id,
                            'account_id': account.id,
                            'name': f'{account.code} {account.name}',
                            'code': account.code,
                            'level': self.hierarchy_level + 1,
                            'foldable': False,
                            'unfolded': True,
                            'has_children': False,
                            'periods': periods,
                            'children': [],
                        })

        # The summary row's own total - the line's own expression(s)
        # evaluated with no extra_domain, i.e. across every account, not
        # just one. This is the figure that matters when the row is
        # collapsed (a Balance Sheet category total, or Trial Balance's
        # grand Total row), and it's independent of whichever individual
        # accounts happen to be listed below it once expanded.
        periods = self._compute_periods(options_list)

        return {
            'id': self.id,
            'real_line_id': self.id,
            'name': self.name,
            'code': self.code,
            'level': self.hierarchy_level,
            'foldable': is_foldable,
            'unfolded': unfolded,
            'has_children': True,
            'periods': periods,
            'children': children,
        }

    def _get_drilldown_domain(self, options, expression_label=None, account_id=None):
        self.ensure_one()
        expression = False
        if expression_label:
            expression = self.expression_ids.filtered(lambda e: e.label == expression_label)
        if not expression and self.expression_ids:
            expression = self.expression_ids[:1]

        if not expression:
            if self.children_ids:
                domains = []
                for child in self.children_ids:
                    child_domain = child._get_drilldown_domain(options, expression_label, account_id=account_id)
                    if child_domain and child_domain != [('id', '=', 0)]:
                        domains.append(child_domain)
                if domains:
                    return list(Domain.OR(domains))
            return [('id', '=', 0)]

        extra_domain = [('account_id', '=', account_id)] if account_id else None
        _value, domains = expression[0]._evaluate(options, extra_domain=extra_domain)
        if not domains:
            return [('id', '=', 0)]

        # Domain.OR (not a hand-rolled ['|', ...] splice): each domain in
        # `domains` can itself carry several implicitly-ANDed conditions
        # (company/posted-state/date/account_type, ...), and a bare '|'
        # prefix only combines the next *two* leaves in polish notation, not
        # two whole multi-condition lists - splicing '|' in front of them
        # silently produces the wrong boolean expression (this was the
        # cause of drilldown's journal-item list summing to something
        # other than the cell it was drilled down from, on any 'aggregation'
        # expression combining more than one sub-domain, e.g. Balance
        # Sheet's Total Assets = Current Assets + Non-current Assets).
        return list(Domain.OR(domains))

    @api.model
    def action_get_drilldown(self, line_id=None, options=None, expression_label=None, account_id=None, **kwargs):
        """Public RPC entry point used by the OWL frontend when a user
        clicks a report cell or kebab action: returns an act_window opening the exact
        journal items that contributed to that cell's value."""
        if options is None and 'options' in kwargs:
            options = kwargs['options']
        if expression_label is None and 'expression_label' in kwargs:
            expression_label = kwargs['expression_label']
        if account_id is None and 'account_id' in kwargs:
            account_id = kwargs['account_id']

        if isinstance(line_id, (list, tuple)):
            line_id = line_id[0] if line_id else None

        line = self.env['account.report.line']
        if line_id:
            try:
                line = self.browse(int(line_id)).exists()
            except (ValueError, TypeError):
                pass

        if line:
            resolved_options = line.report_id._get_default_options(options or {})
            domain = line._get_drilldown_domain(resolved_options, expression_label, account_id=account_id)
            title = line.name
            if account_id:
                account = self.env['account.account'].browse(int(account_id)).exists()
                if account:
                    title = f"{account.code} {account.name}"
            elif expression_label:
                title = f"{line.name} — {expression_label}"
        elif account_id:
            account = self.env['account.account'].browse(int(account_id)).exists()
            title = f"{account.code} {account.name}" if account else "Journal Items"
            domain = [('account_id', '=', int(account_id))]
            if options and isinstance(options, dict):
                if options.get('date_from'):
                    domain.append(('date', '>=', options['date_from']))
                if options.get('date_to'):
                    domain.append(('date', '<=', options['date_to']))
                if not options.get('all_entries'):
                    domain.append(('parent_state', '=', 'posted'))
                if options.get('journal_ids'):
                    domain.append(('journal_id', 'in', options['journal_ids']))
        else:
            return {'type': 'ir.actions.act_window_close'}

        view_id = self.env.ref('account.view_move_line_tree', raise_if_not_found=False)
        search_view_id = self.env.ref('account.view_account_move_line_filter', raise_if_not_found=False)

        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'views': [(view_id.id if view_id else False, 'list'), (False, 'form')],
            'search_view_id': [search_view_id.id, search_view_id.name] if search_view_id else False,
            'domain': domain,
            'context': dict(self.env.context, search_default_posted=1),
        }

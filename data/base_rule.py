from abc import ABC, abstractmethod
from typing import List, Dict

class BaseRule(ABC):
    def __init__(self, rule_id, category_code, set_id, or_and_flag, value_date_flag, amount_flag):
        self.rule_id = rule_id
        self.category_code = category_code
        self.set_id = set_id
        self.or_and_flag = or_and_flag
        self.value_date_flag = value_date_flag
        self.amount_flag = amount_flag
        self.filter1 = None  # Placeholder for the first leg/filter values
        self.filter2 = None  # Placeholder for the second leg/filter values
        self.parsing_info = {"filter1": {}, "filter2": {}}  # Dictionary to store parsed rule cases

    def add_filter1(self, ls_flag, dc_flag, fields: List['Field']):
        self.filter1 = {
            'ls_flag': ls_flag,
            'dc_flag': dc_flag,
            'fields': fields
        }
        self._update_parsing_info('filter1', fields)

    def add_filter2(self, ls_flag, dc_flag, fields: List['Field']):
        self.filter2 = {
            'ls_flag': ls_flag,
            'dc_flag': dc_flag,
            'fields': fields
        }
        self._update_parsing_info('filter2', fields)

    def check_amount_flag_condition(self, field_name: str, flag_value: str, relationship_group: pd.DataFrame) -> bool:
        """Checks the AMOUNT field based on the amount_flag condition for the relationship group."""
        # Separate credit and debit transactions
        credit_txns = relationship_group[relationship_group['TRANSACTION_TYPE'] == 'Credit']
        debit_txns = relationship_group[relationship_group['TRANSACTION_TYPE'] == 'Debit']

        # Ensure there is at least one credit and one debit transaction
        if credit_txns.empty or debit_txns.empty:
            return False

        # Calculate the net amount for credit and debit transactions
        credit_amount = credit_txns[field_name].sum()
        debit_amount = debit_txns[field_name].sum()

        # Net difference between credit and debit amounts
        net_diff = abs(credit_amount - debit_amount)

        # Handle the flag conditions
        if flag_value == 'Same':
            return credit_amount == debit_amount
        elif flag_value.startswith('Different'):
            # Split the flag (e.g., 'Different|LE|50' -> 'Different', 'LE', '50')
            _, operator, threshold = flag_value.split('|')
            threshold = float(threshold)

            # Perform the checks based on the operator
            if operator == 'LE':
                return net_diff <= threshold
            elif operator == 'L':
                return net_diff < threshold
            elif operator == 'GE':
                return net_diff >= threshold
            elif operator == 'G':
                return net_diff > threshold
        return False

    def _update_parsing_info(self, filter_key, fields: List['Field']):
        """Update parsing information dictionary based on the field's flags."""
        for field in fields:
            if field.perf_ref_flag:
                self.parsing_info[filter_key].setdefault('PerfectReference', []).append(field.name)
            if field.valdt_flag:
                self.parsing_info[filter_key].setdefault('ValueDate', []).append(field.name)
            if field.op_flag:
                self.parsing_info[filter_key].setdefault('Operation', []).append(field.name)
            # Add more cases as needed based on the flags

    @abstractmethod
    def valid_rule_values(self):
        """Abstract method for validating if corresponding rule cases are present."""
        pass

import re
from typing import List, Dict

class Field:
    def __init__(self, name, alias, value):
        self.name = name
        self.alias = alias
        self.value = value
        self.id = None
        self.exp_flag = False
        self.valdt_flag = False
        self.op_flag = False
        self.perf_ref_flag = False
        self.perf_ref_params = {}

        self.split_values, self.op_params = self._parse_value()
        self.search_agg_exp = self._create_search_agg_exp()

    def _parse_value(self):
        split_values = []
        op_params = []

        parts = re.split(r'\|(\w+)\|', self.value)
        parts = [part for part in parts if part]

        i = 0
        while i < len(parts):
            identifier = parts[i]
            content = parts[i + 1]

            if identifier == 'EXACT':
                split_values.append({'exact': content})
            elif identifier == 'EXP':
                self.exp_flag = True
                split_values.append({'exp': content})
            elif identifier == 'FRMT':
                self.valdt_flag = True
                self.valdt_params = {"date_format": content.strip()}
            elif identifier == 'OP':
                self.op_flag = True
                op_params.append({"op_details": content.strip()})
            elif identifier == 'PerfRef':
                self.perf_ref_flag = True
                id_val, ref_type, _, length_range = content.split('|')
                self.perf_ref_params = {
                    "id": id_val,
                    "type": ref_type,
                    "length_range": tuple(map(int, length_range.split('-')))
                }
                self.id = id_val
            i += 2

        return split_values, op_params

    def _create_search_agg_exp(self):
        parts = []
        for value in self.split_values:
            if 'exact' in value:
                parts.append(re.escape(value['exact']))
            if 'exp' in value:
                parts.append(value['exp'])
        return ''.join(parts)

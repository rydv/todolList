from typing import List, Dict
from elasticsearch import Elasticsearch
from difflib import SequenceMatcher

class PerfRefRule(BaseRule):
    def __init__(self, rule_id, category_code, set_id, or_and_flag, value_date_flag, amount_flag, es_client: Elasticsearch, index_name: str, scroll_size=100):
        super().__init__(rule_id, category_code, set_id, or_and_flag, value_date_flag, amount_flag)
        self.es_client = es_client
        self.index_name = index_name
        self.scroll_size = scroll_size

    def valid_rule_values(self) -> bool:
        """Validate that the rule has the required filter values set for PerfRef processing."""
        if not self.filter1 or not self.filter2:
            return False
        # Check if the necessary fields for PerfRef are present
        return 'PerfectReference' in self.parsing_info['filter1'] and 'PerfectReference' in self.parsing_info['filter2']

    def find_top_5_common_substrings(self, ref1: str, ref3: str) -> List[str]:
        """Find the top 5 longest common substrings between ref1 and ref3."""
        match = SequenceMatcher(None, ref1, ref3).get_matching_blocks()
        substrings = sorted([ref1[m.a:m.a+m.size] for m in match if m.size >= 5], key=len, reverse=True)
        return substrings[:5]  # Return top 5 longest substrings

    def validate_and_mark(self, group_data: Dict, min_len=5, max_len=15) -> bool:
        """Validate and mark relationship groups based on common substrings."""
        ref1 = group_data.get('Ref1', '')
        ref3 = group_data.get('Ref3', '')
        common_substrings = self.find_top_5_common_substrings(ref1, ref3)

        for substring in common_substrings:
            if min_len <= len(substring) <= max_len:
                return True  # Mark as matched

        return False

    def process_rule(self) -> List[Dict]:
        """Process the PerfRef rule and return matched relationship groups."""
        if not self.valid_rule_values():
            raise ValueError("Invalid rule values for PerfRef processing.")

        scroll_id = None
        matched_groups = []

        while True:
            if scroll_id:
                response = self.es_client.scroll(scroll_id=scroll_id, scroll='1m')
            else:
                response = self.es_client.search(
                    index=self.index_name,
                    body={"query": {"match_all": {}}},
                    scroll='1m',
                    size=self.scroll_size
                )

            scroll_id = response['_scroll_id']
            hits = response['hits']['hits']

            if not hits:
                break

            for hit in hits:
                group_data = hit['_source']
                if self.validate_and_mark(group_data):
                    matched_groups.append(group_data)  # Store matched groups

        return matched_groups

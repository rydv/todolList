from typing import List, Dict, Tuple
from elasticsearch import Elasticsearch
from difflib import SequenceMatcher
from collections import defaultdict

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
        # Ensure filters have 'PerfRef' for Ref1 and Ref3 fields
        return 'PerfRef' in self.parsing_info['filter1'] and 'PerfRef' in self.parsing_info['filter2']

    def _filter_query_formatter(self) -> Dict:
        """Format query based on rule parameters."""
        query = {
            "bool": {
                "must": [
                    {"term": {"category_code": self.category_code}},
                    {"term": {"set_id": self.set_id}}
                ]
            }
        }

        # Additional filters based on flags or other attributes
        if self.value_date_flag:
            query['bool']['must'].append({"exists": {"field": "value_date"}})
        if self.amount_flag:
            query['bool']['must'].append({"exists": {"field": "amount"}})

        return {"query": query}

    def _scroll_transactions(self, scroll_id=None) -> Tuple[str, List[Dict]]:
        """Helper function to fetch transactions using Elasticsearch scroll API."""
        if scroll_id:
            response = self.es_client.scroll(scroll_id=scroll_id, scroll='1m')
        else:
            response = self.es_client.search(
                index=self.index_name,
                body=self._filter_query_formatter(),
                scroll='1m',
                size=self.scroll_size
            )

        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']
        transactions = [hit['_source'] for hit in hits]
        return scroll_id, transactions

    def group_transactions_by_relationship(self, transactions: List[Dict]) -> Dict[str, List[Dict]]:
        """Group transactions by RELATIONSHIP_ID."""
        grouped_transactions = defaultdict(list)
        for txn in transactions:
            relationship_id = txn['RELATIONSHIP_ID']
            grouped_transactions[relationship_id].append(txn)
        return grouped_transactions

    def find_top_5_common_substrings(self, ref1: str, ref3: str) -> List[str]:
        """Find the top 5 longest common substrings between ref1 and ref3."""
        match = SequenceMatcher(None, ref1, ref3).get_matching_blocks()
        substrings = sorted([ref1[m.a:m.a+m.size] for m in match if m.size >= 5], key=len, reverse=True)
        return substrings[:5]  # Return top 5 longest substrings

    def validate_and_mark(self, txn_group: List[Dict], min_len=5, max_len=15) -> Tuple[bool, List[str]]:
        """Validate and mark relationship groups based on common substrings."""
        if len(txn_group) != 2:
            return False, []  # Only consider groups with exactly two transactions

        # Extract the REFERENCE field from both transactions
        ref1 = txn_group[0].get('REFERENCE', '')
        ref3 = txn_group[1].get('REFERENCE', '')

        # Ensure both references are provided and non-empty
        if not ref1 or not ref3:
            return False, []

        # Find common substrings between the two references
        common_substrings = self.find_top_5_common_substrings(ref1, ref3)

        # Filter substrings based on the length criteria
        valid_substrings = [substring for substring in common_substrings if min_len <= len(substring) <= max_len]

        # Return True if any valid substrings exist, along with the list of valid substrings
        return bool(valid_substrings), valid_substrings

    def find_matches(self) -> pd.DataFrame:
        """Find matched relationship groups based on the PerfRef rule and return a DataFrame."""
        # Validate the rule
        if not self.valid_rule_values():
            raise ValueError("Invalid rule values for PerfRef processing.")

        matched_transactions = []  # Initialize list to store matched transactions
        scroll_id = None

        while True:
            # Fetch transactions and scroll id
            scroll_id, transactions = self._scroll_transactions(scroll_id)

            if not transactions:
                break  # Exit loop when no more transactions

            # Group transactions by RELATIONSHIP_ID
            grouped_transactions = self.group_transactions_by_relationship(transactions)

            # Process each group
            for relationship_id, txn_group in grouped_transactions.items():
                is_matched, matched_substrings = self.validate_and_mark(txn_group)
                if is_matched:
                    # Create DataFrame from the transaction group
                    txn_group_df = pd.DataFrame(txn_group)

                    # Add matched_value field to the DataFrame
                    txn_group_df['MATCHED_VALUE'] = ', '.join(matched_substrings)  # Join substrings into one string

                    # Append to matched_transactions list
                    matched_transactions.append(txn_group_df)

        # Concatenate all DataFrames in the list into a single DataFrame
        if matched_transactions:
            final_df = pd.concat(matched_transactions, ignore_index=True)

            # Apply amount flag filter if self.amount_flag is set
            if self.amount_flag:
                final_df = final_df.groupby('RELATIONSHIP_ID').filter(
                    lambda group: self.check_amount_flag_condition('AMOUNT', self.amount_flag, group)
                )

            # Reset index
            final_df.reset_index(drop=True, inplace=True)

            # Add Rule Id column
            final_df['Rule Id'] = self.rule_id

            return final_df

        return pd.DataFrame()  # Return an empty DataFrame if no matches found

class RuleEngine:
    def __init__(self):
        self.rules = {}

    def register_rule(self, rule_name, rule_class):
        self.rules[rule_name] = rule_class

    def apply_rule(self, rule_name, *args, **kwargs):
        rule_class = self.rules.get(rule_name)
        if rule_class:
            rule_instance = rule_class(*args, **kwargs)
            return rule_instance.process_rule()
        else:
            raise ValueError(f"Rule {rule_name} not found.")

# Initialize Elasticsearch client
es_client = Elasticsearch()

# Register the PerfRefRule in the rule engine
rule_engine = RuleEngine()
rule_engine.register_rule('PerfRefRule', PerfRefRule)

# Apply the PerfRefRule to process data
matched_relationship_groups = rule_engine.apply_rule('PerfRefRule', es_client, 'your_index_name')

package identity

import future.keywords.if
import future.keywords.in

# ---------------------------------------------------------------------------
# Default deny - all decisions must be explicitly allowed
# ---------------------------------------------------------------------------

default allow_issuance = false
default allow_delegation = false
default allow_validation = false

# ---------------------------------------------------------------------------
# Tier configuration
# ---------------------------------------------------------------------------

tier_max_ttl := {
    "T0": 3600,
    "T1": 1800,
    "T2": 900,
    "T3": 300,
}

tier_max_delegation_depth := {
    "T0": 0,
    "T1": 2,
    "T2": 1,
    "T3": 0,
}

# Tier ordering: lower number = higher trust
tier_level := {
    "T0": 0,
    "T1": 1,
    "T2": 2,
    "T3": 3,
}

# ---------------------------------------------------------------------------
# Identity Issuance Policy
# ---------------------------------------------------------------------------

# Allow identity issuance if:
# 1. The subject has a valid SPIFFE ID from the correct trust domain
# 2. The requested tier is valid
# 3. The requested TTL does not exceed the tier maximum
allow_issuance if {
    valid_spiffe_id(input.subject_spiffe_id)
    input.requested_tier in {"T0", "T1", "T2", "T3"}
    ttl_within_limit(input.requested_tier, input.requested_ttl)
}

# ---------------------------------------------------------------------------
# Delegation Policy
# ---------------------------------------------------------------------------

# Allow delegation if:
# 1. The delegator has a valid SPIFFE ID
# 2. The delegation depth does not exceed the tier limit
# 3. The delegate tier is not higher trust than the delegator
allow_delegation if {
    valid_spiffe_id(input.delegator_spiffe_id)
    valid_spiffe_id(input.delegate_spiffe_id)
    depth_within_limit(input.delegator_tier, input.current_depth)
    not delegate_higher_trust(input.delegator_tier, input.delegate_tier)
}

# ---------------------------------------------------------------------------
# Token Validation Policy
# ---------------------------------------------------------------------------

allow_validation if {
    valid_spiffe_id(input.subject_spiffe_id)
    input.tier in {"T0", "T1", "T2", "T3"}
    not token_expired(input.exp, input.current_time)
}

# ---------------------------------------------------------------------------
# Helper Rules
# ---------------------------------------------------------------------------

# Valid SPIFFE ID: must start with spiffe:// and match our trust domain
valid_spiffe_id(spiffe_id) if {
    startswith(spiffe_id, "spiffe://")
    parts := split(spiffe_id, "/")
    count(parts) >= 4
    parts[2] == input.trust_domain
}

valid_spiffe_id(spiffe_id) if {
    startswith(spiffe_id, "spiffe://")
    parts := split(spiffe_id, "/")
    count(parts) >= 4
    # Allow if trust_domain not in input (for direct calls)
    not input.trust_domain
}

# TTL check: requested TTL must not exceed the tier maximum
ttl_within_limit(tier, requested_ttl) if {
    max := tier_max_ttl[tier]
    requested_ttl <= max
}

ttl_within_limit(tier, _) if {
    # If no TTL requested, it will be set to the tier default — always ok
    not input.requested_ttl
}

# Depth check: current delegation chain depth must not exceed tier maximum
depth_within_limit(delegator_tier, current_depth) if {
    max_depth := tier_max_delegation_depth[delegator_tier]
    current_depth < max_depth
}

# Delegate cannot have higher trust level than the delegator
delegate_higher_trust(delegator_tier, delegate_tier) if {
    tier_level[delegate_tier] < tier_level[delegator_tier]
}

# Token is expired if current_time > exp
token_expired(exp, current_time) if {
    current_time > exp
}

# ---------------------------------------------------------------------------
# Decision Audit - always emit a decision record
# ---------------------------------------------------------------------------

decision_id := crypto.md5(json.marshal({
    "input": input,
    "timestamp": time.now_ns(),
}))

decision_record := {
    "decision_id": decision_id,
    "allow_issuance": allow_issuance,
    "allow_delegation": allow_delegation,
    "allow_validation": allow_validation,
    "input_hash": crypto.md5(json.marshal(input)),
    "timestamp": time.now_ns(),
}

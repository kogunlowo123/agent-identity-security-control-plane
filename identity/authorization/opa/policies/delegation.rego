package delegation

import future.keywords.if
import future.keywords.in

# ---------------------------------------------------------------------------
# Default deny
# ---------------------------------------------------------------------------

default allow = false
default chain_valid = false

# ---------------------------------------------------------------------------
# Delegation Chain Validation
# ---------------------------------------------------------------------------

# A delegation chain is valid if:
# 1. Every link in the chain is individually valid
# 2. The chain depth does not exceed the root delegator's tier limit
# 3. Each delegate's capabilities are a subset of the delegator's
# 4. The chain has not been revoked
allow if {
    chain_valid
    not chain_revoked
}

chain_valid if {
    count(input.chain) > 0
    every_link_valid
    depth_within_limit
    capabilities_subset_at_each_link
}

# ---------------------------------------------------------------------------
# Per-link validation
# ---------------------------------------------------------------------------

every_link_valid if {
    every link in input.chain {
        link_valid(link)
    }
}

link_valid(link) if {
    # Must have required fields
    link.delegator != ""
    link.delegate != ""
    link.not_before != 0
    link.not_after != 0

    # Time validity
    input.current_time >= link.not_before
    input.current_time <= link.not_after

    # Signature present
    link.signature != ""
}

# ---------------------------------------------------------------------------
# Depth limit
# ---------------------------------------------------------------------------

tier_max_depth := {
    "T0": 0,
    "T1": 2,
    "T2": 1,
    "T3": 0,
}

depth_within_limit if {
    chain_depth := count(input.chain)
    root_tier := input.chain[0].delegator_tier
    max_depth := tier_max_depth[root_tier]
    chain_depth <= max_depth
}

# ---------------------------------------------------------------------------
# Capability subset check
# ---------------------------------------------------------------------------

capabilities_subset_at_each_link if {
    every i in numbers.range(0, count(input.chain) - 1) {
        link := input.chain[i]
        next_link := input.chain[i + 1]
        # Every capability of the next link's delegate must be in this link's capabilities
        every cap in next_link.capabilities {
            cap in link.capabilities
        }
    }
}

# ---------------------------------------------------------------------------
# Revocation check
# ---------------------------------------------------------------------------

chain_revoked if {
    some link in input.chain
    link.delegator in input.revoked_principals
}

chain_revoked if {
    some link in input.chain
    link.delegate in input.revoked_principals
}

chain_revoked if {
    some link in input.chain
    link.jti in input.revoked_jtis
}

# ---------------------------------------------------------------------------
# Decision record
# ---------------------------------------------------------------------------

decision_record := {
    "allow": allow,
    "chain_valid": chain_valid,
    "chain_length": count(input.chain),
    "timestamp": time.now_ns(),
}

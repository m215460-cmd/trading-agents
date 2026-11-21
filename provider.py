def get_market_snapshot():
    # No source configured: fail closed, never invent prices.
    return {"status":"not_configured","quotes":[],"as_of":None,"source":None,"market_indices":[]}

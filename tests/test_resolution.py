from src.resolution import EntityResolver


def test_seed_entity_resolution():
    resolver = EntityResolver()

    # Test OpenAI variations
    for name in ["OpenAI", "Open AI", "OpenAI, Inc.", "openai inc"]:
        canonical, method, conf = resolver.resolve(name)
        assert canonical == "OpenAI"
        assert conf >= 0.90

    # Test Anthropic variations
    for name in ["Anthropic PBC", "anthropic ai", "Anthropic"]:
        canonical, method, conf = resolver.resolve(name)
        assert canonical == "Anthropic"

    # Test Unknown Entity Normalization
    canonical, method, conf = resolver.resolve("Future Autonomous Labs Inc.")
    assert canonical == "Future Autonomous"
    assert method == "RULE_NORMALIZATION"
import re
from typing import Dict, Tuple

# Seed List of foundational AI startups & enterprises
SEED_AI_ENTITIES = {
    "OpenAI": ["openai", "open ai", "openai inc", "openai, inc.", "openai limited"],
    "Anthropic": ["anthropic", "anthropic pbc", "anthropic ai"],
    "Mistral AI": ["mistral", "mistral ai", "mistral.ai", "mistral ai sas"],
    "Cohere": ["cohere", "cohere inc", "cohere ai"],
    "Perplexity": ["perplexity", "perplexity ai", "perplexity inc"],
    "DeepMind": ["google deepmind", "deepmind technologies", "deep mind"],
    "Hugging Face": ["hugging face", "huggingface", "hugging face inc"],
    "Scale AI": ["scale ai", "scale computing", "scale.ai"],
    "Databricks": ["databricks", "databricks inc"],
    "Midjourney": ["midjourney", "midjourney inc"],
    "Stability AI": ["stability ai", "stability.ai", "stability ai ltd"],
    "ElevenLabs": ["elevenlabs", "eleven labs", "elevenlabs inc"],
    "Runway": ["runway", "runway ml", "runwayml", "runway ai, inc."],
    "Jasper": ["jasper", "jasper ai", "jasper.ai"],
    "Character.AI": ["character ai", "character.ai", "character technologies"],
    "Glean": ["glean", "glean technologies"],
    "Pinecone": ["pinecone", "pinecone systems", "pinecone io"],
    "Weaviate": ["weaviate", "weaviate b.v."],
    "Qdrant": ["qdrant", "qdrant solutions"],
    "LangChain": ["langchain", "langchain inc"],
    "LlamaIndex": ["llamaindex", "llama index", "runllama"],
    "Anysphere": ["anysphere", "cursor ai", "cursor"],
    "Poolside": ["poolside", "poolside ai"],
    "Together AI": ["together ai", "together computer"],
    "Groq": ["groq", "groq inc"],
    "Cerebras Systems": ["cerebras", "cerebras systems"],
    "SambaNova Systems": ["sambanova", "sambanova systems inc"],
    "Modular": ["modular", "modular ai", "modular inc"],
    "Harvey": ["harvey", "harvey ai"],
    "Decagon": ["decagon", "decagon ai"],
    "Cognition": ["cognition", "cognition labs", "devin ai"],
    "Synthesia": ["synthesia", "synthesia ltd"],
    "Shield AI": ["shield ai", "shield ai inc"],
    "Weights & Biases": ["wandb", "weights and biases", "weights & biases"],
    "Writer": ["writer", "writer ai", "writer inc"],
    "Adept": ["adept", "adept ai", "adept labs"],
    "Inflection AI": ["inflection", "inflection ai"],
    "Pika Labs": ["pika", "pika labs", "pika art"],
    "Suno": ["suno", "suno ai"],
    "Udio": ["udio", "uncharted labs"],
    "Phind": ["phind", "phind ai"],
    "Baseten": ["baseten", "baseten inc"],
    "Replicate": ["replicate", "replicate inc"],
    "Modal": ["modal", "modal labs"],
    "Fireworks AI": ["fireworks", "fireworks ai"],
    "Unstructured": ["unstructured", "unstructured io"],
    "CoreWeave": ["coreweave", "coreweave inc"],
    "Lambda Labs": ["lambda", "lambda labs"],
}

LEGAL_SUFFIXES_REGEX = re.compile(
    r"\b(inc|incorporated|corp|corporation|ltd|limited|llc|pbc|gmbh|sas|b\.v\.|technologies|technology|ai|labs|systems)\b",
    re.IGNORECASE,
)


class EntityResolver:

    def __init__(self):
        # Invert seed mapping for O(1) lookup
        self.alias_to_canonical: Dict[str, str] = {}
        for canonical, aliases in SEED_AI_ENTITIES.items():
            self.alias_to_canonical[canonical.lower()] = canonical
            for alias in aliases:
                self.alias_to_canonical[alias.lower()] = canonical

    def _normalize_string(self, text: str) -> str:
        """Strips punctuation, legal suffixes, and collapses whitespace."""
        cleaned = re.sub(r"[^\w\s]", " ", text)
        cleaned = LEGAL_SUFFIXES_REGEX.sub(" ", cleaned)
        return " ".join(cleaned.lower().split())

    def resolve(self, raw_name: str) -> Tuple[str, str, float]:
        """Resolves a raw entity string to its canonical representation.

        Returns: (canonical_name, method, confidence)
        """
        if not raw_name or not raw_name.strip():
            return ("Unknown", "NONE", 0.0)

        cleaned_raw = raw_name.strip()
        lower_raw = cleaned_raw.lower()

        # Step 1: Direct Seed Match
        if lower_raw in self.alias_to_canonical:
            return (self.alias_to_canonical[lower_raw], "SEED_EXACT", 1.0)

        # Step 2: Normalized Seed Match
        normalized = self._normalize_string(lower_raw)
        if normalized in self.alias_to_canonical:
            return (self.alias_to_canonical[normalized], "SEED_NORMALIZED", 0.95)

        # Step 3: Seed substring containment check
        for alias, canonical in self.alias_to_canonical.items():
            if (
                len(alias) > 3
                and (f" {alias} " in f" {lower_raw} ")
                or (lower_raw == alias)
            ):
                return (canonical, "SEED_SUBSTRING", 0.90)

        # Step 4: Rule-based Title Case Normalization
        title_cased = " ".join(
            word.capitalize() for word in self._normalize_string(raw_name).split()
        )
        if not title_cased:
            title_cased = raw_name.strip().title()

        return (title_cased, "RULE_NORMALIZATION", 0.80)
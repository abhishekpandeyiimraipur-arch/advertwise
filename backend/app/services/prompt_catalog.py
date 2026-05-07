import os
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RenderedPrompt:
    system_prompt: str
    user_prompt: str
    model_requirements: dict


class PromptCatalog:
    """
    Loads prompt YAML/JSON templates from app/prompts/.
    render() returns a RenderedPrompt with system_prompt,
    user_prompt, and model_requirements.

    For MVP: if a prompt file is not found, returns a
    sensible stub so workers don't crash during development.
    Prompt YAML files are built in a separate pass.
    """

    PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

    # Default token budgets per prompt name (used when file missing)
    DEFAULT_BUDGETS = {
        "framework-router":              {"max_tokens": 600},
        "script-generate":               {"max_tokens": 500},
        "script-refine":                 {"max_tokens": 400},
        "script-critic":                 {"max_tokens": 400},
    }

    def render(
        self,
        name: str,
        version: str,
        variables: dict = None
    ) -> RenderedPrompt:
        """
        Renders a prompt template with given variables.
        Falls back to stub prompts if template file not found.
        """
        variables = variables or {}

        # Try loading from YAML/JSON file
        for ext in [".yaml", ".yml", ".json"]:
            path = self.PROMPTS_DIR / f"{name}.v{version.replace('.', '_')}{ext}"
            if path.exists():
                try:
                    return self._load_and_render(path, variables)
                except Exception as e:
                    logger.warning(
                        f"Prompt file {path} found but failed to load: {e}. "
                        f"Using stub."
                    )
                    break

        # Stub fallback — returns minimal valid prompt
        logger.warning(
            f"Prompt '{name}' v{version} not found in {self.PROMPTS_DIR}. "
            f"Using stub prompt. Add YAML file before production."
        )
        budget = self.DEFAULT_BUDGETS.get(name, {"max_tokens": 500})
        return RenderedPrompt(
            system_prompt=(
                f"You are an expert AI assistant for Indian D2C advertising. "
                f"Task: {name}. Respond with valid JSON only."
            ),
            user_prompt=f"Input data: {json.dumps(variables, ensure_ascii=False)}",
            model_requirements=budget,
        )

    def _load_and_render(self, path: Path, variables: dict) -> RenderedPrompt:
        """Load a YAML/JSON prompt file and substitute variables."""
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix in [".yaml", ".yml"]:
                template = yaml.safe_load(f)
            else:
                template = json.load(f)

        system_prompt = template.get("system_prompt", "")
        user_prompt = template.get("user_prompt_template", "")

        # Simple variable substitution: {{variable_name}}
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            user_prompt = user_prompt.replace(
                placeholder,
                json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list)) else str(value)
            )

        return RenderedPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_requirements=template.get(
                "model_requirements",
                {"max_tokens": 500}
            ),
        )


# Singleton — one instance per process
_catalog_instance = None

def get_prompt_catalog() -> PromptCatalog:
    global _catalog_instance
    if _catalog_instance is None:
        _catalog_instance = PromptCatalog()
    return _catalog_instance

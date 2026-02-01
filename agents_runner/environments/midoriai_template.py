from __future__ import annotations

from agents_runner.environments.storage import load_environments
from agents_runner.environments.storage import save_environment
from agents_runner.midoriai_template import MidoriAITemplateDetection
from agents_runner.midoriai_template import scan_midoriai_agents_template

from .model import Environment


def apply_midoriai_template_detection(
    env: Environment, *, workspace_root: str
) -> MidoriAITemplateDetection:
    detection = scan_midoriai_agents_template(workspace_root)
    env.midoriai_template_likelihood = detection.midoriai_template_likelihood
    env.midoriai_template_detected = detection.midoriai_template_detected
    env.midoriai_template_detected_path = detection.midoriai_template_detected_path
    return detection


def refresh_environment_midoriai_template_detection(
    env_id: str, *, workspace_root: str
) -> MidoriAITemplateDetection | None:
    env_id = str(env_id or "").strip()
    if not env_id:
        return None
    envs = load_environments()
    env = envs.get(env_id)
    if env is None:
        return None
    detection = apply_midoriai_template_detection(env, workspace_root=workspace_root)
    save_environment(env)
    return detection

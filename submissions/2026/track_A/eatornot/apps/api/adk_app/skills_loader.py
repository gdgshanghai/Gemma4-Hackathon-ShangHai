"""Skills Loader — 从 /skills 目录加载 ADK Skills"""

import pathlib
import logging

logger = logging.getLogger(__name__)


def load_skill_instructions() -> dict[str, str]:
    """
    从 skills/ 目录加载所有 SKILL.md 的内容。
    返回 {skill_name: instruction_content} 字典。
    """
    # __file__ = apps/api/adk_app/skills_loader.py
    # parents[0] = adk_app/
    # parents[1] = api/
    # parents[2] = apps/
    # parents[3] = eatornot/
    root = pathlib.Path(__file__).resolve().parents[3]  # eatornot/
    skills_root = root / "skills"

    skill_dirs = [
        "weight-loss-skill",
        "nutrition-balance-skill",
        "controlled-indulgence-skill",
        "spending-control-skill",
        "mcdonalds-order-skill",
    ]

    skills = {}
    for skill_name in skill_dirs:
        skill_dir = skills_root / skill_name
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding="utf-8")
            # 去掉 frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            skills[skill_name] = content
            logger.info(f"Loaded skill: {skill_name}")
        else:
            logger.warning(f"Skill not found: {skill_md}")

    return skills


def build_skill_instructions() -> str:
    """构建包含所有 skill 的综合指令文本"""
    skills = load_skill_instructions()
    if not skills:
        return ""

    parts = ["## Domain Skills\n"]
    for name, content in skills.items():
        parts.append(f"### {name}\n{content}\n")

    return "\n".join(parts)

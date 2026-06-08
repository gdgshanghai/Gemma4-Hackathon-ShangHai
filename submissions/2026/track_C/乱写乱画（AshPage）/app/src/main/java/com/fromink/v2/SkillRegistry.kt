package com.fromink.v2

import android.content.Context
import android.util.Log

private const val SKILLS_ASSET_DIR = "skills"
private const val TAG = "FromInkSkillRegistry"

data class SkillDefinition(
    val name: String,
    val description: String,
    val content: String,
)

class SkillRegistry(context: Context) {
    private val assetManager = context.assets
    private val skills: Map<String, SkillDefinition> by lazy { loadSkills() }

    fun catalogText(): String {
        if (skills.isEmpty()) {
            return "(no skills found)"
        }
        return skills.values
            .sortedBy { it.name }
            .joinToString("\n") { "- ${it.name}: ${it.description}" }
    }

    fun loadSkill(name: String): SkillDefinition? = skills[name]

    fun skillNames(): List<String> = skills.keys.sorted()

    private fun loadSkills(): Map<String, SkillDefinition> {
        val directories = assetManager.list(SKILLS_ASSET_DIR).orEmpty()
        val loadedSkills = buildMap {
            for (directory in directories.sorted()) {
                val path = "$SKILLS_ASSET_DIR/$directory/SKILL.md"
                val raw = runCatching {
                    assetManager.open(path).bufferedReader().use { it.readText() }
                }.getOrNull() ?: continue
                val metadata = parseFrontmatter(raw)
                val name = metadata["name"].orEmpty().ifBlank { directory }
                val description = metadata["description"].orEmpty().ifBlank {
                    raw.lineSequence()
                        .firstOrNull { it.startsWith("#") }
                        ?.trimStart('#', ' ')
                        .orEmpty()
                        .ifBlank { "No description." }
                }
                put(name, SkillDefinition(name, description, raw))
            }
        }
        if (BuildConfig.DEBUG) {
            Log.d(
                TAG,
                "loaded skills count=${loadedSkills.size}, names=${loadedSkills.keys.sorted().joinToString()}",
            )
        }
        return loadedSkills
    }

    private fun parseFrontmatter(raw: String): Map<String, String> {
        if (!raw.startsWith("---\n")) {
            return emptyMap()
        }
        val end = raw.indexOf("\n---", startIndex = 4)
        if (end == -1) {
            return emptyMap()
        }
        return raw.substring(4, end)
            .lineSequence()
            .mapNotNull { line ->
                val separatorIndex = line.indexOf(':')
                if (separatorIndex <= 0) {
                    null
                } else {
                    val key = line.substring(0, separatorIndex).trim()
                    val value = line.substring(separatorIndex + 1).trim().trim('"')
                    key to value
                }
            }
            .toMap()
    }
}

package com.fromink.v2

import android.util.Log
import com.google.ai.edge.litertlm.Tool
import com.google.ai.edge.litertlm.ToolParam
import com.google.ai.edge.litertlm.ToolSet

private const val TAG = "FromInkSkillTool"

class SkillToolSet(
    private val skillRegistry: SkillRegistry,
) : ToolSet {
    @Tool(
        description = "Load the full content of a skill by exact name. " +
            "Use this only when the user's request clearly needs the named method.",
    )
    fun loadSkill(
        @ToolParam(description = "Exact skill name from the catalog, for example mao-zedong-thought.")
        name: String,
    ): Map<String, String> {
        val normalizedName = name.trim()
        SkillUsageTracker.record(normalizedName, "called")
        if (BuildConfig.DEBUG) {
            Log.d(TAG, "loadSkill called with name=$normalizedName")
        }
        val skill = skillRegistry.loadSkill(normalizedName)
        if (skill == null) {
            SkillUsageTracker.record(normalizedName, "not_found")
            if (BuildConfig.DEBUG) {
                Log.d(
                    TAG,
                    "loadSkill miss name=$normalizedName, available=${skillRegistry.skillNames().joinToString()}",
                )
            }
            return mapOf(
                "status" to "not_found",
                "name" to normalizedName,
                "available_skills" to skillRegistry.skillNames().joinToString(", "),
            )
        }
        if (BuildConfig.DEBUG) {
            Log.d(
                TAG,
                "loadSkill hit name=${skill.name}, description=${skill.description.take(80)}",
            )
        }
        SkillUsageTracker.record(skill.name, "ok")
        return mapOf(
            "status" to "ok",
            "name" to skill.name,
            "description" to skill.description,
            "content" to skill.content,
        )
    }
}

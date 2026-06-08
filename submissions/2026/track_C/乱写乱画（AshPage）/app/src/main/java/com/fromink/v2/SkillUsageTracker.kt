package com.fromink.v2

data class SkillUsageStatus(
    val called: Boolean,
    val name: String? = null,
    val status: String = "not_called",
)

object SkillUsageTracker {
    @Volatile
    private var current = SkillUsageStatus(called = false)

    @Synchronized
    fun reset() {
        current = SkillUsageStatus(called = false)
    }

    @Synchronized
    fun record(name: String, status: String) {
        current = SkillUsageStatus(
            called = true,
            name = name,
            status = status,
        )
    }

    @Synchronized
    fun snapshot(): SkillUsageStatus = current
}

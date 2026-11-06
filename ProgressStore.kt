package com.openai.cyberlab.data

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

class ProgressStore(context: Context) {
    private val prefs = context.getSharedPreferences("cyberlab_progress", Context.MODE_PRIVATE)

    var learner by mutableStateOf(prefs.getString("learner", "") ?: "")
        private set
    var xp by mutableIntStateOf(prefs.getInt("xp", 0))
        private set
    var completedLessons by mutableStateOf(
        (prefs.getStringSet("completed_lessons", emptySet()) ?: emptySet()).toSet()
    )
        private set
    var completedLabs by mutableStateOf(
        (prefs.getStringSet("completed_labs", emptySet()) ?: emptySet()).toSet()
    )
        private set
    var checklistDone by mutableStateOf(
        (prefs.getStringSet("checklist", emptySet()) ?: emptySet()).toSet()
    )
        private set

    val level: Int get() = xp / 250 + 1
    val levelProgress: Float get() = (xp % 250) / 250f

    fun setLearner(value: String) {
        learner = value.trim().ifBlank { "Learner" }
        prefs.edit().putString("learner", learner).apply()
    }

    fun completeLesson(id: String, reward: Int): Boolean {
        if (id in completedLessons) return false
        completedLessons = completedLessons + id
        xp += reward
        persist()
        return true
    }

    fun completeLab(id: String, reward: Int): Boolean {
        if (id in completedLabs) return false
        completedLabs = completedLabs + id
        xp += reward
        persist()
        return true
    }

    fun toggleChecklist(id: String) {
        checklistDone = if (id in checklistDone) checklistDone - id else checklistDone + id
        persist()
    }

    private fun persist() {
        prefs.edit()
            .putInt("xp", xp)
            .putStringSet("completed_lessons", HashSet(completedLessons))
            .putStringSet("completed_labs", HashSet(completedLabs))
            .putStringSet("checklist", HashSet(checklistDone))
            .apply()
    }
}
